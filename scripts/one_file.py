#!/usr/bin/env python

from log_parser import *

import sys

if __name__ == "__main__":
    assert(len(sys.argv) > 1)
    with open(sys.argv[1]) as f:
        lines = f.readlines()
    print_benchmarks(parse_one_log(lines))
