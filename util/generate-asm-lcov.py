#!/usr/bin/python
# Copyright (c) 2016, Google Inc.
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION
# OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
# CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
import os
import os.path
import subprocess
import sys

# The LCOV output format for each source file is:
#
# SF:<filename>
# DA:<line>,<execution count>
# ...
# end_of_record
#
# The <execution count> can either be 0 for an unexecuted instruction or a
# value representing the number of executions. The DA line should be omitted
# for lines not representing an instruction.

SECTION_SEPERATOR = '-' * 80

def is_asm(l):
  """Returns whether a line should be considered to be an instruction."""
  l = l.strip()
  # Empty lines
  if l == '':
    return False
  # Comments
  if l.startswith('#'):
    return False
  # Assembly Macros
  if l.startswith('.'):
    return False
  # Label
  if l.endswith(':'):
    return False
  return True

def merge(callgrind_files, srcs):
  """Calls callgrind_annotate over the set of callgrind output
  |callgrind_files| using the sources |srcs| and merges the results
  together."""
  out = ''
  for file in callgrind_files:
    data = subprocess.check_output(['callgrind_annotate', file] + srcs)
    out += '%s\n%s\n' % (data, SECTION_SEPERATOR)
  return out

def parse(filename, data, current):
  """Parses an annotated execution flow |data| from callgrind_annotate for
  source |filename| and updates the current execution counts from |current|."""
  with open(filename) as f:
    source = f.read().split('\n')

  out = current
  if out == None:
    out = [0 if is_asm(l) else None for l in source]

  # Lines are of the following formats:
  #   -- line: Indicates that analysis continues from a different place.
  #   =>     : Indicates a call/jump in the control flow.
  #   <Count> <Code>: Indicates that the line has been executed that many times.
  line = None
  for l in data:
    l = l.strip() + ' '
    if l.startswith('-- line'):
      line = int(l.split(' ')[2]) - 1
    elif line != None and '=>' not in l:
      count = l.split(' ')[0].replace(',', '').replace('.', '0')
      instruction = l.split(' ', 1)[1].strip()
      if count != '0' or is_asm(instruction):
        if out[line] == None:
          out[line] = 0
        out[line] += int(count)
      line += 1

  return out


def generate(data):
  """Parses the merged callgrind_annotate output |data| and generates execution
  counts for all annotated files."""
  out = {}
  data = [p.strip() for p in data.split(SECTION_SEPERATOR)]


  # Most sections are ignored, but a section with:
  #  User-annotated source: <file>
  # precedes a listing of execution count for that <file>.
  for i in range(len(data)):
    if 'User-annotated source' in data[i] and i < len(data) - 1:
      filename = data[i].split(':', 1)[1].strip()
      res = data[i + 1]
      if filename not in out:
        out[filename] = None
      if 'No information' in res:
        res = []
      else:
        res = res.split('\n')
      out[filename] = parse(filename, res, out[filename])
  return out

def output(data):
  """Takes a dictionary |data| of filenames and execution counts and generates
  a LCOV coverage output."""
  out = ''
  for filename, counts in data.iteritems():
    out += 'SF:%s\n' % (os.path.abspath(filename))
    for line, count in enumerate(counts):
      if count != None:
        out += 'DA:%d,%s\n' % (line + 1, count)
    out += 'end_of_record\n'
  return out

if __name__ == '__main__':
  if len(sys.argv) != 3:
    print '%s <Callgrind Folder> <Build Folder>' % (__file__)
    sys.exit()

  cg_folder = sys.argv[1]
  build_folder = sys.argv[2]

  cg_files = []
  for (cwd, _, files) in os.walk(cg_folder):
    for f in files:
      if f.startswith('callgrind.out'):
        cg_files.append(os.path.abspath(os.path.join(cwd, f)))

  srcs = []
  for (cwd, _, files) in os.walk(build_folder):
    for f in files:
      fn = os.path.join(cwd, f)
      if fn.endswith('.S'):
        srcs.append(fn)

  annotated = merge(cg_files, srcs)
  lcov = generate(annotated)
  print output(lcov)
