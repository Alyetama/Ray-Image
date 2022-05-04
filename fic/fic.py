#!/usr/bin/env python
# coding: utf-8

import argparse
import imghdr
import shutil
import signal
import sys
import time
from glob import glob
from pathlib import Path
from typing import Optional, Union

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


def size_change(original_size, compressed_size, file, out_file):
    change = str((float(compressed_size) - float(original_size)) /
                 float(original_size) * 100)
    if 0 < float(change):
        change = f'(\033[31m+{change[:4]}%\033[39m) [Skipped...]'
        if file and out_file:
            Path(out_file).unlink()
            shutil.copy(file, out_file)
    else:
        change = f'({change[:5]}%)'
    return change


def compress(file: str,
             quality: int = 70,
             overwrite: bool = False,
             no_subsampling: bool = False,
             output_dir: Optional[str] = None) -> Union[str, None]:

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

    file = Path(file)

    if overwrite:
        out_file = file
    else:
        out_file = f'{file.with_suffix("")}_compressed{file.suffix}'

    if output_dir:
        out_file = f'{file.with_suffix("")}{file.suffix}'
        out_parent = f'{output_dir}/{Path(Path(out_file).parent).name}'
        if not Path(out_parent).exists():
            Path(out_parent).mkdir(exist_ok=True, parents=True)
        out_file = f'{out_parent}/{Path(out_file).name}'

    im = Image.open(file)
    if file.suffix.lower() in ['.jpg', '.jpeg']:
        f_suffix = 'JPEG'
    else:
        f_suffix = file.suffix.upper()[1:]

    if no_subsampling and f_suffix == 'JPEG':
        im.save(out_file,
                f_suffix,
                optimize=True,
                quality=quality,
                subsampling='keep')
    else:
        im.save(out_file, f_suffix, optimize=True, quality=quality)

    original_size = str(Path(file).stat().st_size / 1000)[:5]
    compressed_size = str(Path(out_file).stat().st_size / 1000)[:5]

    display_fname = Path(file).name
    if len(display_fname) > 12:
        display_fname = f'{Path(file).stem[:12]}..{Path(file).suffix}'

    f_name = f'\033[37m\033[40m{display_fname}\033[49m\033[39m'
    o_size = f'{original_size} kB'
    c_size = f'\033[30m\033[42m{compressed_size} kB\033[49m\033[39m'

    change = size_change(original_size, compressed_size, file, out_file)

    took = round(time.time() - start, 2)
    print(f'🚀 {f_name}: {o_size} ==> {c_size} {change} | {took}s')
    return out_file


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
                        help='Output image quality (default: 70)')
    parser.add_argument('--overwrite',
                        action='store_true',
                        help='Overwrite the original image')
    parser.add_argument(
        '-N',
        '--no-subsampling',
        action='store_true',
        help='Turn off subsampling and retain the original image setting '
        '(JPEG only)')
    parser.add_argument('-s',
                        '--silent',
                        action='store_true',
                        help='Silent mode')
    parser.add_argument(
        'path',
        nargs='+',
        help='Path to a single file/directory or multiple files/directories')
    return parser.parse_args()


def main(path, output_dir, quality, no_subsampling, silent, overwrite,
         **kwargs) -> Union[list, str]:
    session_start = time.time()
    signal.signal(signal.SIGINT, keyboard_interrupt_handler)

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

    if len(files) > 1:
        futures = []
        for file in files:
            futures.append(
                compress_many.remote(file=file,
                                     quality=quality,
                                     overwrite=overwrite,
                                     no_subsampling=no_subsampling,
                                     output_dir=output_dir))
        results = []
        for future in tqdm(futures):
            results.append(ray.get(future))
        ray.shutdown()

    else:
        return compress(file=files[0],
                        quality=quality,
                        overwrite=overwrite,
                        no_subsampling=no_subsampling,
                        output_dir=output_dir)

    files = [x for x in files if x]
    files_size = round(
        sum([Path(x).stat().st_size
             for x in files if Path(x).exists()]) / 1e+6, 2)
    results = [x for x in results if x]
    results_size = round(
        sum([Path(x).stat().st_size
             for x in results if Path(x).exists()]) / 1e+6, 2)

    change = size_change(files_size, results_size, None, None)
    print('\nTotal:')
    print(f'    Before: \033[31m{files_size} MB\033[39m')
    print(f'    After: \033[32m{results_size} MB {change}\033[39m')
    print(f'Took: {round(time.time() - session_start, 2)}s')
    return results


if __name__ == '__main__':
    args = opts()
    main(**vars(args))
