#!/usr/bin/env python
# coding: utf-8

from .fic import main as _main, opts


def main():
    args = opts()
    _main(**vars(args))
