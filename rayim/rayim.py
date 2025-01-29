#!/usr/bin/env python
# coding: utf-8

import argparse
import copy
import imghdr
import io
import os
import shutil
import signal
import sys
import time
from glob import glob
from pathlib import Path
from typing import IO, Optional, Tuple, Union

import ray
from PIL import Image
from tqdm import tqdm


def keyboard_interrupt_handler(sig: int, _) -> None:
    print(f'KeyboardInterrupt (ID: {sig}) has been caught...')
    try:
        ray.shutdown()
    except NameError:
        pass
    print('Terminating the session gracefully...')
    sys.exit(1)


def size_change(original_size: float, compressed_size: float) -> tuple:
    change = (compressed_size - original_size) / original_size * 100
    if 0 < change:
        return (
            f'(\033[31m+{round(change, 4)}%\033[39m) [\033[33mSkipped...\033['
            f'39m]', False)
    else:
        return f'({round(change, 4)}%)', True


def save_img(file_object: Union[IO, Path, str],
             im: Image.Image,
             no_subsampling: bool,
             f_suffix: str,
             quality: int,
             to_jpeg: bool,
             optimize: bool = False) -> None:

    if no_subsampling and f_suffix == 'JPEG':
        im.save(file_object,
                f_suffix,
                optimize=optimize,
                quality=quality,
                subsampling='keep')
    else:
        if to_jpeg:
            f_suffix = 'JPEG'
            im = im.convert('RGB')
        im.save(file_object, f_suffix, optimize=optimize, quality=quality)


def compress(file: str,
             quality: int = 70,
             overwrite: bool = False,
             no_subsampling: bool = False,
             to_jpeg: bool = False,
             size: Optional[Tuple[int]] = None,
             div_by: Optional[float] = None,
             output_dir: Optional[str] = None,
             optimize: bool = False,
             keep_date: bool = False) -> Optional[str]:

    start = time.time()

    if output_dir and not Path(output_dir).exists():
        Path(output_dir).mkdir(exist_ok=True, parents=True)

    if not Path(file).exists():
        print(f'\033[41m`{file}` does not exist! Skipping...\033[49m')
        return

    if not imghdr.what(file):
        print(f'\033[41m`{file}` does not appear to be a valid image file! '
              'Skipping...\033[49m')
        return

    file_stats = os.stat(file)
    file = Path(file)
    original_file_suffix = file.suffix
    size_1 = Path(file).stat().st_size

    original_size = str(Path(file).stat().st_size / 1000)[:5]

    if overwrite:
        out_file = copy.deepcopy(file)
    elif to_jpeg:
        out_file = f'{file.with_suffix("")}_compressed.jpg'
    else:
        out_file = f'{file.with_suffix("")}_compressed{original_file_suffix}'

    if output_dir:
        out_file = f'{file.with_suffix("")}{file.suffix}'
        out_parent = f'{output_dir}/{Path(Path(out_file).parent).name}'
        if not Path(out_parent).exists():
            Path(out_parent).mkdir(exist_ok=True, parents=True)
        out_file = f'{out_parent}/{Path(out_file).name}'

    im = Image.open(file)

    if div_by or size:
        if div_by:
            size = [int(x // div_by) for x in im.size]
        im = im.resize(size)

    if file.suffix:
        if file.suffix.lower() in ['.jpg', '.jpeg']:
            f_suffix = 'JPEG'
        else:
            f_suffix = file.suffix.upper()[1:]
    else:
        f_suffix = 'JPEG'

    if file.suffix.lower() == '.png' and not to_jpeg:
        quality = 100

    tmp_img_obj = io.BytesIO()
    save_img(tmp_img_obj, im, no_subsampling, f_suffix, quality, to_jpeg,
             optimize)

    compressed_size = str(sys.getsizeof(tmp_img_obj) / 1000)[:5]

    file_stem = Path(file).stem
    if len(file_stem) > 12:
        dots = '\033[35m...\033[39m'
        display_fname = f'{file_stem[:12]}{dots}{Path(file).suffix}'
    else:
        display_fname = Path(file).name

    f_name = f'\033[37m\033[40m{display_fname}\033[49m\033[39m'
    o_size = f'{original_size} kB'
    c_size = f'\033[30m\033[42m{compressed_size} kB\033[49m\033[39m'

    change, change_exists = size_change(float(original_size),
                                        float(compressed_size))

    if not to_jpeg:
        out_file = Path(out_file).with_suffix(original_file_suffix)
    else:
        out_file = Path(out_file).with_suffix('.jpg')
    if change_exists:
        save_img(out_file, im, no_subsampling, f_suffix, quality, to_jpeg,
                 optimize)

    if to_jpeg and overwrite:
        if Path(out_file).name != file.name:
            file.unlink()

    if Path(out_file).exists():
        size_2 = Path(out_file).stat().st_size
    else:
        size_2 = size_1

    if keep_date:
        os.utime(out_file, (file_stats.st_atime, file_stats.st_mtime))

    took = round(time.time() - start, 2)
    if sys.stdout.isatty():
        print(f'🚀 {f_name}: {o_size} ==> {c_size} {change} | {took}s')
    else:
        print(f'🚀 {display_fname}: {original_size} kB ==> {compressed_size} '
              f'kB {change} | {took}s')
    return out_file, size_1, size_2


@ray.remote
def compress_many(**kwargs) -> str:
    return compress(**kwargs)


def opts() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-o',
        '--output-dir',
        type=str,
        help='Output directory (default: next to original file)')
    parser.add_argument('-q',
                        '--quality',
                        default=70,
                        type=int,
                        help='Output image quality (JPEG only; default: 70)')
    parser.add_argument('--overwrite',
                        action='store_true',
                        help='Overwrite the original image')
    parser.add_argument(
        '-n',
        '--no-subsampling',
        action='store_true',
        help='Turn off subsampling and retain the original image setting '
        '(JPEG only)')
    parser.add_argument('-j',
                        '--to-jpeg',
                        action='store_true',
                        help='Convert the image(s) to .JPEG')
    parser.add_argument(
        '--replicate-dir-tree',
        action='store_true',
        help='Replicate the source directory tree in the output')
    parser.add_argument('-s',
                        '--size',
                        nargs=2,
                        type=int,
                        help='Resize the image to WIDTH HEIGHT')
    parser.add_argument('-d',
                        '--div-by',
                        type=float,
                        help='Divide the image size (WxH) by a factor of n')
    parser.add_argument('-S',
                        '--silent',
                        action='store_true',
                        help='Silent mode')
    parser.add_argument('-O',
                        '--optimize',
                        action='store_true',
                        help='Apply default optimization on the image(s)')
    parser.add_argument(
        '-k',
        '--keep-date',
        action='store_true',
        help='Keep the original modification date')
    parser.add_argument(
        'path',
        nargs='+',
        help='Path to a single file/directory or multiple files/directories')
    return parser.parse_args()


def rayim(path: list,
          output_dir=None,
          quality=70,
          no_subsampling=False,
          silent=False,
          overwrite=False,
          to_jpeg=False,
          replicate_dir_tree=False,
          size=None,
          div_by=None,
          optimize=False,
          keep_date=False) -> Union[list, Optional[str]]:
    session_start = time.time()
    signal.signal(signal.SIGINT, keyboard_interrupt_handler)

    if div_by and size:
        raise Exception('Can\'t use both `size` and `div_by`!')

    if silent:
        sys.stdout = None
        sys.stderr = None

    if any(Path(x).is_dir() for x in path):
        _files = []
        for _input in path:
            if Path(_input).is_dir():
                imgs = [
                    glob(f'{_input}/**/*{x}', recursive=True) for x in
                    ['.jpg', '.JPG', '.jpeg', '.JPEG', '.PNG', '.png']
                ]
                imgs = sum(imgs, [])
                _files.append(imgs)
            else:
                _files.append(_input)

        if any(isinstance(x, list) for x in _files):
            files = [x for x in path if not Path(x).is_dir()] + sum(
                [x if isinstance(x, list) else [x] for x in _files], [])
        else:
            files = [x for x in path if not Path(x).is_dir()] + _files
    else:
        files = path

    files = [x for x in files if Path(x).exists()]
    if not files:
        print('Found no existing files to process.')
        sys.exit(0)

    if quality > 100:
        raise AssertionError('`--quality` value can\'t be higher then 100!')

    if replicate_dir_tree:
        if len(path) > 1:
            raise AssertionError(
                'Can only replicate source tree for one input directory!')
        shutil.copytree(path[0], f'{path[0]}_original')

    if len(files) > 1:
        futures = []
        for file in files:
            if replicate_dir_tree:
                overwrite = True
            futures.append(
                compress_many.remote(file=file,
                                     quality=quality,
                                     overwrite=overwrite,
                                     no_subsampling=no_subsampling,
                                     output_dir=output_dir,
                                     to_jpeg=to_jpeg,
                                     size=size,
                                     div_by=div_by,
                                     optimize=optimize,
                                     keep_date=keep_date))
        results = []
        for future in tqdm(futures):
            result = ray.get(future)
            if result:
                results.append(result)
        ray.shutdown()

    else:
        return compress(file=files[0],
                        quality=quality,
                        overwrite=overwrite,
                        no_subsampling=no_subsampling,
                        output_dir=output_dir,
                        to_jpeg=to_jpeg,
                        size=size,
                        div_by=div_by,
                        optimize=optimize,
                        keep_date=keep_date)

    files_size = round(sum([x[1] for x in results]), 2) / 1e+6
    results_size = round(sum([x[2] for x in results]), 2) / 1e+6

    change = size_change(files_size, results_size)
    print('\nTotal:')
    print(f'    Before: \033[31m{files_size} MB\033[39m')
    print(f'    After: \033[32m{results_size} MB {change[0]}\033[39m')
    print(f'Took: {round(time.time() - session_start, 2)}s')
    return results


def main() -> None:
    os.environ['RAY_DEDUP_LOGS'] = '0'
    args = opts()
    _ = rayim(path=args.path,
              output_dir=args.output_dir,
              quality=args.quality,
              no_subsampling=args.no_subsampling,
              silent=args.silent,
              replicate_dir_tree=args.replicate_dir_tree,
              overwrite=args.overwrite,
              to_jpeg=args.to_jpeg,
              size=args.size,
              div_by=args.div_by,
              optimize=args.optimize,
              keep_date=args.keep_date)


if __name__ == '__main__':
    main()
