#!/usr/bin/env python
from log_parser import *

def latex_imath(text):
    return "$" + text + "$"

def latexify_params(benchmark):
    return latex_imath(", ".join(k + " = " + str(v) for k, v in sorted(benchmark.params.iteritems())))

class LatexTable:
    def __init__(self, alignment):
        self.rows = []
        self.alignment = alignment

    def append(self, row):
        assert (len(row) == len(self.alignment))
        self.rows.append(row)

    def prepend(self, row):
        assert (len(row) == len(self.alignment))
        self.rows = [row] + self.rows

    def __getitem__(self, index):
        return self.rows[index]

    def __or__(self, other):
        assert (len(self.rows) == len(other.rows))
        result = LatexTable(self.alignment + other.alignment)
        for r1, r2 in zip(self.rows, other.rows):
            result.append(r1 + r2)
        return result

    def __str__(self):
        s = ""
        s += (r"\begin{tabular}{%s}" % self.alignment) + "\n"
        for r in self.rows:
            s += " & ".join(map(str, r)) + r"\\" + "\n"
        s += r"\end{tabular}" + "\n"
        return s

    def __eq__(self, other):
        return self.alignment == other.alignment and self.rows == other.rows

def data_table_from_benchmarks(benchmarks, kind):
    table = LatexTable("rrr")
    for b in benchmarks:
        table.append([str(b[kind][k]) for k in ["Min", "p50", "p90"]])
    return table

def param_table_from_benchmarks(benchmarks):
    table = LatexTable("l")
    for b in benchmarks:
        table.append([latexify_params(b)])
    return table

def interleave_rows(t1, t2):
    assert (t1.alignment == t2.alignment)
    result = LatexTable(t1.alignment)
    for r1, r2 in zip(t1, t2):
        result.append(r1)
        result.append(r2)
    return result

def print_interleaved_table(p100, v100, name, kind1, kind2, comment = ""):
    p100 = filter_keep(p100, name)
    v100 = filter_keep(v100, name)

    th = param_table_from_benchmarks(p100)
    assert (th == param_table_from_benchmarks(v100))
    th = interleave_rows(th, param_table_from_benchmarks(p100))
    th.prepend([""])
    th.prepend([""])
    t1 = data_table_from_benchmarks(p100, kind1)
    t11 = data_table_from_benchmarks(p100, kind2)
    t1 = interleave_rows(t1, t11)
    t1.prepend(["p0", "p50", "p90"])
    t1.prepend(["", "Pascal", ""])
    t2 = data_table_from_benchmarks(v100, kind1)
    t21 = data_table_from_benchmarks(v100, kind2)
    t2 = interleave_rows(t2, t21)
    t2.prepend(["p0", "p50", "p90"])
    t2.prepend(["", "Volta", ""])

    i = 0
    for r in t1:
        i += 1

    ts = LatexTable("l")
    ts.append([""])
    ts.append([""])
    for j in range(i/2 - 1):
        ts.append([kind1])
        ts.append([kind2])

    print "%", comment, kind1, kind2
    print (th | ts | t1 | t2)


def print_table(p100, v100, comment = "", kind = "autotuned"):
    th = param_table_from_benchmarks(p100)
    assert (th == param_table_from_benchmarks(v100))
    th.prepend([""])
    th.prepend([""])
    t1 = data_table_from_benchmarks(p100, kind)
    t1.prepend(["p0", "p50", "p90"])
    t1.prepend(["", "Pascal", ""])
    t2 = data_table_from_benchmarks(v100, kind)
    t2.prepend(["p0", "p50", "p90"])
    t2.prepend(["", "Volta", ""])
    print "%", comment, kind
    print (th | t1 | t2)

def filter_keep(benchmarks, name):
    result = []
    for b in benchmarks:
        if name in b.name:
            result.append(b)
    return result

def print_combined(p100, v100, name, kind):
    print_table(filter_keep(p100, name), filter_keep(v100, name), name, kind)


if __name__ == "__main__":
    with open("P100.txt") as f:
        lines = f.readlines()
        p100 = parse_one_log(lines)
    with open("V100.txt") as f:
        lines = f.readlines()
        v100 = parse_one_log(lines)

    p100 = aggregate_kronecker(p100)
    v100 = aggregate_kronecker(v100)
    
    print_combined(p100, v100, "Kronecker", "autotuned")
    print_combined(p100, v100, "Kronecker", "C2")
    print_combined(p100, v100, "WaveNet", "autotuned")
    for n in ["1LUT", "2LUT", "MLP1", "MLP3", "BatchMatMul", "GroupConvolution", "GroupNormalization", "TransposedMatMul"]:
        print_interleaved_table(p100, v100, n, "autotuned", "Caffe2", n)
