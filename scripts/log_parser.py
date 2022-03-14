#!/usr/bin/env python

import sys
import os

archs = {"P100", "V100"}
types = {"C2", "Caffe2", "autotuned", "ATen", "ATenAsMatMul", "Caffe2AsMatMul"}
keywords = archs | types

# Parses the line
#[ RUN      ] BatchMatMul.TransposedBatchMatMul_C2_P100_B_500_K_26_M_72_N_26
#
# Returns a tuple:
#   benchmark name -> BatchMatMul.TransposedBatchMatMul
#   kind           -> C2   (listed in types above)
#   arch           -> P100 (listed in archs above)
#   params         -> dict "name" -> value
def extract_bench_and_params(line):
    global archs
    global types

    start = line.find("]") + 2
    line = line[start:]
    words = line.split("_")
    kind = None
    arch = None
    params = {}

    prev_param = None
    name = None
    for i in xrange(1, len(words)):
        word = words[i]
        # Collect name with underscores until kind or arch is found
        if name is None:
            if word in archs or word in types:
                name = "_".join(words[:i])
            else:
                continue

        if word in archs:
            if arch is None:
                arch = word
            else:
                print "[WARNING] duplicate arch found: ", arch, " + ", word
                print "in ", line,
            continue
        if word in types:
            if kind is None:
                kind = word
            else:
                print "[WARNING] duplicate kind found: ", kind, " + ", word
                print "in ", line,
            continue

        if prev_param is None:
            prev_param = word
        else:
            params[prev_param] = int(word)
            prev_param = None
    if prev_param is not None:
        raise ValueError("malformed parameter list in\n" + line)
    if kind is None:
        print "[WARNING] could not find kind in " + line,
        print "          expected one of " + str(types)
        print "          assigning \"naive\""
        kind = "naive"
    if arch is None:
        raise ValueError("could not find arch in\n" + line + "\nexpected one of " + str(archs))

    return (name, kind, arch, params)

class PerfKeys:
    KEYS = ["Min", "p50", "p90", "p99", "Max"]

# Parses
#Min: 110us, p50: 115us, p90: 118us, p99: 127us, Max: 127us
# Returns dict with key from PerfKeys and value as integer time in us
def parse_perfs_line(line):
    array = line.split(",")
    array = map(lambda x: x.strip(), array)
    pairs = map(lambda x: x.split(": "), array)
    perfs = {}
    for p in pairs:
        if p[1][-2:] != "us":
            raise ValueError("expected times in us, got %s" % p[1])
        if p[0] not in PerfKeys.KEYS:
            raise ValueError("unknown perf key %s" % p[0])
        perfs[p[0]] = int(p[1][:-2])
    return perfs

class Benchmark:
    def __init__(self, name, arch, params):
        self.name = name
        self.params = params
        self.arch = arch
        self.tc = dict()
        self.c2 = dict()
        self.aten = dict()
        self.naive = dict()

    def __textualize_params(self):
        return "_".join(p + "_" + str(self.params[p]) for p in sorted(self.params))

    def __readable_params(self):
        return ", ".join(p + " = " + str(self.params[p]) for p in sorted(self.params))

    def __eq__(self, b):
        return self.name == b.name and self.arch == b.arch \
            and self.__textualize_params() == b.__textualize_params()

    def __str__(self):
        return self.name + " @" + self.arch + " with " + self.__readable_params()

    mapping = {"ATen": "aten", "C2": "c2", "Caffe2": "c2", "autotuned": "tc", "ATenAsMatMul": "aten", "Caffe2AsMatMul": "c2", "naive": "naive"}

    def __getitem__(self, kind):
        assert(kind in Benchmark.mapping)
        return self.__dict__[Benchmark.mapping[kind]]

    def __setitem__(self, kind, value):
        assert(kind in Benchmark.mapping)
        self.__dict__[Benchmark.mapping[kind]] = value

class ParseState:
    EXPECT_RUN = 1
    EXPECT_COMPILED_STATS = 2
    EXPECT_COMPILED_TIMINGS = 3
    EXPECT_CPU_STATS = 4
    EXPECT_CPU_TIMINGS = 5
    EXPECT_REFERENCE_STATS = 6
    EXPECT_REFERENCE_TIMINGS = 7
    EXPECT_OK = 8

class LineType:
    OTHER = 0
    RUN = 1
    OK = 2
    FAIL = 3
    COMPILED_STATS = 4
    CPU_STATS = 5
    REFERENCE_STATS = 6
    TIMINGS = 7

def line_type(line):
    if "[ RUN" in line:
        return LineType.RUN
    elif "OK ]" in line:
        return LineType.OK
    elif " FAILED " in line and " (" in line:
        return LineType.FAIL
    elif "COMPILED KERNEL STATS" in line:
        return LineType.COMPILED_STATS
    elif "+ CPU STATS" in line:
        return LineType.CPU_STATS
    elif "REFERENCE IMPL. STATS" in line:
        return LineType.REFERENCE_STATS
    elif "Min: " in line and "us" in line:
        return LineType.TIMINGS
    else:
        return LineType.OTHER

def set_timings_none(timings):
    for k in PerfKeys.KEYS:
        timings[k] = None

def parse_one_log(lines):
    state = ParseState.EXPECT_RUN
    benchmarks = []
    timings = None
    current_bench = None
    for i, line in enumerate(lines):
        lt = line_type(line)
        if lt == LineType.OTHER:
            continue
        if lt == LineType.FAIL:
            print "[WARNING] found failed test for " + str(current_bench)
            print "          setting values to None"
            set_timings_none(timings)
            state = ParseState.EXPECT_RUN
            continue

        if state == ParseState.EXPECT_RUN:
            if lt == LineType.RUN:
                bench, kind, arch, params = extract_bench_and_params(line)

                # Find the corresponding benchmark descriptor,
                # insert one first if it does not exist
                benchmark = Benchmark(bench, arch, params)
                if benchmark not in benchmarks:
                    benchmarks.append(benchmark)
                idx = benchmarks.index(benchmark)
                current_bench = benchmarks[idx]
                # Store the reference to the timings dict of the appropriate
                # benchmark kind
                timings = current_bench[kind]

                if kind == "autotuned" or kind == "naive":
                    state = ParseState.EXPECT_COMPILED_STATS
                else:
                    state = ParseState.EXPECT_REFERENCE_STATS
            else:
                raise ValueError("expected RUN line, got\n" + line + "\nat line " + str(i))
        elif state == ParseState.EXPECT_COMPILED_STATS:
            if lt == LineType.COMPILED_STATS:
                state = ParseState.EXPECT_COMPILED_TIMINGS
            elif lt == LineType.OK:
                state = ParseState.EXPECT_RUN
                print "[WARNING] did not find compiled stats for kind " + kind
                print "          for " + str(current_bench)
            else:
                raise ValueError("expected COMPILED_STATS, got\n" + line + "\nat line " + str(i))
        elif state == ParseState.EXPECT_COMPILED_TIMINGS:
            if lt == LineType.TIMINGS:
                parse_perfs_line(line)  # just check it parses, ignore the result
                state = ParseState.EXPECT_CPU_STATS
            else:
                raise ValueError("expected TIMINGS, got\n" + line + "\nat line " + str(i))
        elif state == ParseState.EXPECT_CPU_STATS:
            if lt == LineType.CPU_STATS:
                state = ParseState.EXPECT_CPU_TIMINGS
            else:
                raise ValueError("expected CPU_STATS, got\n" + line + "\nat line " + str(i))
        elif state == ParseState.EXPECT_CPU_TIMINGS:
            if lt == LineType.TIMINGS:
                for k,v in parse_perfs_line(line).iteritems():
                    timings[k] = v
                state = ParseState.EXPECT_OK
            else:
                raise ValueError("expected TIMINGS, got\n" + line + "\nat line " + str(i))
        elif state == ParseState.EXPECT_REFERENCE_STATS:
            if lt == LineType.REFERENCE_STATS:
                state = ParseState.EXPECT_REFERENCE_TIMINGS
            elif lt == LineType.OK:
                state = ParseState.EXPECT_RUN
                print "[WARNING] did not find reference stats for kind " + kind
                print "          for " + str(current_bench)
            else:
                raise ValueError("expected REFERENCE_STATS, got\n" + line + "\nat line " + str(i))
        elif state == ParseState.EXPECT_REFERENCE_TIMINGS:
            if lt == LineType.TIMINGS:
                for k,v in parse_perfs_line(line).iteritems():
                    timings[k] = v
                state = ParseState.EXPECT_OK
            else:
                raise ValueError("expected TIMINGS, got\n" + line + "\nat line " + str(i))
        elif state == ParseState.EXPECT_OK:
            if lt == LineType.OK:
                state = ParseState.EXPECT_RUN
            else:
                raise ValueError("expected OK, got\n" + line + "\nat line " + str(i))

    for b in benchmarks:
        for kind in Benchmark.mapping:
            if len(b[kind]) != 0:
                continue
            print "[WARNING] the log did not contain runtimes of kind " + kind
            print "          for " + str(b)
            print "          inserting None"
            set_timings_none(b[kind])

    return benchmarks

def print_benchmarks(benchmarks):
    for b in benchmarks:
        print b
        print "\tnaive:\t" + "\t".join(k + ": " + str(b.naive[k]) for k in PerfKeys.KEYS)
        print "\tTC:\t" + "\t".join(k + ": " + str(b.tc[k]) for k in PerfKeys.KEYS)
        print "\tCaffe2:\t" + "\t".join(k + ": " + str(b.c2[k]) for k in PerfKeys.KEYS)
        print "\tATen:\t" + "\t".join(k + ": " + str(b.aten[k]) for k in PerfKeys.KEYS)


def insert_commas(value):
    s = str(value)
    r = s[:(len(s) % 3)]
    s = s[(len(s) % 3):]
    assert(len(s) % 3 == 0)
    for i in xrange(0, len(s) / 3):
        r += "," + s[i:i+3]
    while r[0] == ",":
        r = r[1:]
    return r

def gen_param_names(params):
    return r"\times ".join(sorted(params.keys()))

def gen_param_values(params):
    sorted_values = [str(params[k]) for k in sorted(params.keys())]
    return r"\times ".join(sorted_values)

def gen_latex_table_header(n = 1, pr = "", sf = ""):
#    print r"\begin{figure}[htb]"
    print r"\begin{tabular}{%s|l|%s%s}" % (pr, "|".join(["rrr" for i in range(n)]), sf)
    print r"\hline"
    if pr != "": print " & ",
    print r" & %s \\" % " & ".join([" p0 & p50 & p90 " for i in range(n)])
    print r"\hline"

def gen_latex_table_symbolic_params(params):
    print r"\multicolumn{5}{l}{Size $(%s)$} \\" % gen_param_names(params)
    print r"\hline"

def guard_latex_symbols(string):
    return string.replace("\\", "\\backslash ").replace("%", "\\%").replace("_", "\\_").replace("&", "\\&")

def gen_latex_table_footer(bench):
    print r"\end{tabular}"
#    print r"\caption{\label{fig:results_%s} %s}" % (bench, guard_latex_symbols(bench))
#    print r"\end{figure}"

def gen_latex_table_line(perf_single):
    for i in ["Min", "p50", "p90"]:
        if i not in perf_single:
            raise ValueError("%s" % str(perf_single))
    arr = [insert_commas(perf_single[i]) + "us" for i in ["Min", "p50", "p90"]]
    return " & ".join(arr)

def gen_latex_table_na_line(ending):
    return r" N/A & N/A & N/A %s " % ending

def gen_latex_table_hline():
    print r"\hline"

def gen_param_values_cross(params, ending = r"\\", row_header = True):
    st = ""
    if row_header: st += " & "
    st += r"\multicolumn{3}{l}{$(%s)$} %s" % (gen_param_values(params), ending)
    if ending == r"\\": st += r"\hline"
    return st

def gen_param_symbolic_and_value(params):
    return ", ".join(p + "=" + str(params[p]) for p in params)

def gen_param_values_eq(params, ending = "r\\", row_header = True):
    st = ""
    if row_header: st += " & "
    st += r"\multicolumn{3}{p{2.5cm}|}{$%s$} %s" % (gen_param_symbolic_and_value(params), ending)
    if ending == r"\\": st += r"\hline"
    return st

def gen_latex_table_body_impl(strs, perfs, ending = r"\\", row_header = True):
    if row_header: strs[0] += "Caffe2 + CUBLAS          & "
    if "c2" in perfs:
        strs[0] += r"%s %s" % (gen_latex_table_line(perfs["c2"]), ending)
    else:
        strs[0] += gen_latex_table_na_line(ending)

    if row_header: strs[1] += "ATen + CUBLAS            & "
    if "aten" in perfs:
        strs[1] += r"%s %s" % (gen_latex_table_line(perfs["aten"]), ending)
    else:
        strs[1] += gen_latex_table_na_line(ending)
    #print r"\ourtoolkitname~(manual kernel) & %s %s" % (gen_latex_table_line(perfs["baseline_kernel"]), ending)
    if row_header: strs[2] += "\ourtoolkitname~(manual) & "
    strs[2] += r"%s %s" % (gen_latex_table_line(perfs["baseline_total"]), ending)
    #print r"\ourtoolkitname~(autotuned kernel) & %s %s" % (gen_latex_table_line(perfs["autotuned_kernel"]), ending)
    if row_header: strs[3] += "\ourtoolkitname~(autotuned) & "
    strs[3] += r"%s %s" % (gen_latex_table_line(perfs["autotuned_total"]), ending)
    if ending == r"\\": strs[3] += r"\hline"

def gen_latex_table_body(params, perfs):
    strs = ["" for i in range(4)]
    gen_param_values_cross(params)
    gen_latex_table_body_impl(strs, perfs)
    for i in strs:
        print i

def gen_latex_table(bench, param_perfs_array):
    params = param_perfs_array[0][0]
    gen_latex_table_header()
    gen_latex_table_symbolic_params(params)
    for pair in param_perfs_array:
        params, perfs = pair
        gen_latex_table_body(params, perfs)
        gen_latex_table_hline()

    gen_latex_table_footer(bench)

def gen_per_kernel_latex_table(bench, data):
    n_param_sets = len(data[bench])
    gen_latex_table_header(n_param_sets, "|l", "|")
    subdata = data[bench]
    subdata.sort(key=lambda p: reduce(lambda a,b: a*b, p[0].values(), 1))
    ps = ""
    strs = ["" for i in range(4)]
    for i, p in enumerate(subdata):
        params, perfs = p
        ps += gen_param_values_eq(params, "&" if i != len(subdata) - 1 else r"\\", i == 0)
        gen_latex_table_body_impl(strs, perfs, "&" if i != len(subdata) - 1 else r"\\", i == 0)
    print " & ", ps
    for i, s in enumerate(strs):
        if i == 0:
            print (r"\multirow{4}{*}{\rotatebox[origin=c]{90}{%s}} &" % guard_latex_symbols(bench)),
        else:
            print " & ",
        print s
    gen_latex_table_footer(bench)


def gen_consolidated_latex_bench_name(bench, params):
    print r"%s & \multicolumn{4}{l}{$%s$} \\" % (guard_latex_symbols(bench), gen_param_names(params))
    print r"\hline"

# data: dict (bench: string => array(tuple(params, perfs)))
def gen_consolidated_latex_table(data):
    gen_latex_table_header()
    for bench in data:
        params = data[bench][0][0]
        gen_consolidated_latex_bench_name(bench, params)
        for pair in data[bench]:
            gen_latex_table_body(*pair)
            gen_latex_table_hline()
    gen_latex_table_footer("total")

def create_prefix(path):
    path = path.replace(".", "")
    while path[0] == "/":
        path = path[1:]
    while path[-1:] == "/":
        path = path[:-1]
    return path.replace("/","_")

def add_timings(timings1, timings2):
    for k in PerfKeys.KEYS:
        if timings1[k] is None:
            timings1[k] = timings2[k]
        elif timings2[k] is None:
            pass
        else:
            timings1[k] += timings2[k]

def aggregate_kronecker(benchmarks):
    result = []
    for b in benchmarks:
        if "Kronecker3" not in b.name:
            result.append(b)
            continue
        if "Kronecker3_" not in b.name:
            if b not in result:
                result.append(b)
                continue
            pos = result.index(b)
            add_timings(result[pos].tc, b.tc)
            add_timings(result[pos].aten, b.aten)
            add_timings(result[pos].c2, b.c2)
        b.name = "Kronecker.Kronecker3"
        if b not in result:
            result.append(b)
        else:
            pos = result.index(b)
            add_timings(result[pos].tc, b.tc)
    return result

if __name__ == "__main__":
    print "This files should no longer be called directly"
    print
    print "Call ./individual_files.py <directory names> ..."
    print "  to produce per-benchmark tables"
    print
    print "Call ./one_files.py <directory names> ..."
    print "  to produce consolidated per-system tables"

