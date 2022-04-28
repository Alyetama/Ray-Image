# **F**ast **I**mage **C**ompression

*fic*: (**F**)ast (**I**)mage (**C**)ompression

## Requirements

- [Python>=3.6, <3.10](https://www.python.org/downloads/)
- [Ray>=1.0.0](https://github.com/ray-project/ray)

To install `ray`, run\*:
```
pip install ray
```
\*For Apple Silicon (M1), follow the instructions [here](https://docs.ray.io/en/latest/ray-overview/installation.html#m1-mac-apple-silicon-support) to install `ray`.


## Installation

```
pip install fic
```

## Usage

```
usage: fic [-h] [-o OUTPUT_DIR] [-q QUALITY] [--overwrite] [-N] [-s]
           path [path ...]

positional arguments:
  path                  Path to a single file/directory or multiple
                        files/directories

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        Output directory (default: next to original file)
  -q QUALITY, --quality QUALITY
                        Output image quality (default: 80)
  --overwrite           Overwrite the original image
  -N, --no-subsampling  Turn off subsampling and retain the original image
                        setting (JPEG only)
  -s, --silent          Silent mode
  ```

## Examples

- Running on a single file:
```shell
fic foo.jpg
# 🚀 foo.jpg: 1157. kB ==> 619.9 kB (-46.4%) | 0.07s
```

- Running on a folder `foo` and writing the output to `compressed`
```shell
fic foo/ -o compressed
# (compress_many pid=612778) 🚀 foo.jpg: 988.9 kB ==> 544.8 kB (-44.9%) | 0.08s
# (compress_many pid=612828) 🚀 bar.jpg: 983.7 kB ==> 541.2 kB (-44.9%) | 0.07s
# (compress_many pid=612826) 🚀 foobar.jpg: 1001. kB ==> 550.7 kB (-44.9%) | 0.07s
# (compress_many pid=612786) 🚀 barfoo.jpg: 1001. kB ==> 551.9 kB (-44.8%) | 0.08s
# ...

# Total:
#    Before: 1091.32 MB
#    After: 599.46 MB (-45.0%)
```

# Speed comparison

### Test 1 (on Apple Silicon M1, 8-cores)

| Method      | Number of files | Speed |
| ----------- | ----------- | ----------- | 
| Regular compression      | 1,000       | `60.090s` | 
| fic   | 1,000        | **`26.937s`** (**`55.17%`** faster) | 

```YAML
Total:
    Before: 1091.32 MB
    After: 599.46 MB (-45.0%)
```

### Test 2 (on Intel @ 2.299GHz, 32-cores)

| Method      | Number of files | Speed |
| ----------- | ----------- | ----------- |
| Regular compression      | 6,000       | `7m42.919s` |
| fic   | 6,000        | **`5m15.423s`** (**`31.96%`** faster) | 

```YAML
Total:
    Before: 6040.59 MB
    After: 3321.70 MB (-45.0%)
```
