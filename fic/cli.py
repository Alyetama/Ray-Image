from .fic import main as _main, opts


def main():
    args = opts()
    _main(**vars(args))
