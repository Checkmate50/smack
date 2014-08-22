#! /usr/bin/env python

from os import path
import os
import json
import sys
import re
import subprocess
import argparse
import platform
from smackgen import *

VERSION = '1.4.1'


def generateSourceErrorTrace(boogieOutput, bpl):
  FILENAME = '[\w#$~%.\/-]+'
  LABEL = '[\w$]+'

  if not re.search('.*{:sourceloc \"(' + FILENAME + ')\", (\d+), (\d+)}.*', bpl):
    # no debug info in bpl file
    return None

  sourceTrace = '\nSMACK verifier version ' + VERSION + '\n\n'
  for traceLine in boogieOutput.splitlines(True):
    resultMatch = re.match('Boogie .* (\d+) verified, (\d+) error.*', traceLine)
    traceMatch = re.match('([ ]+)(' + FILENAME + ')\((\d+),(\d+)\): (' + LABEL + ')', traceLine)
    errorMatch = re.match('(' + FILENAME + ')\((\d+),(\d+)\): (.*)', traceLine)
    if resultMatch:
      verified = int(resultMatch.group(1))
      errors = int(resultMatch.group(2))
      sourceTrace += '\nFinished with ' + str(verified) + ' verified, ' + str(errors) + ' errors\n'
    elif traceMatch:
      spaces = str(traceMatch.group(1))
      filename = str(traceMatch.group(2))
      lineno = int(traceMatch.group(3))
      colno = int(traceMatch.group(4))
      label = str(traceMatch.group(5))

      for bplLine in bpl.splitlines(True)[lineno:lineno+10]:
        m = re.match('.*{:sourceloc \"(' + FILENAME + ')\", (\d+), (\d+)}.*', bplLine)
        if m:
          filename = str(m.group(1))
          lineno = int(m.group(2))
          colno = int(m.group(3))
 
          sourceTrace += spaces + filename + '(' + str(lineno) + ',' + str(colno) + ')\n'
          break
    elif errorMatch:
      filename = str(errorMatch.group(1))
      lineno = int(errorMatch.group(2))
      colno = int(errorMatch.group(3))
      message = str(errorMatch.group(4))
 
      for bplLine in bpl.splitlines(True)[lineno-2:lineno+8]:
        m = re.match('.*{:sourceloc \"(' + FILENAME + ')\", (\d+), (\d+)}.*', bplLine)
        if m:
          filename = str(m.group(1))
          lineno = int(m.group(2))
          colno = int(m.group(3))
 
          sourceTrace += filename + '(' + str(lineno) + ',' + str(colno) + '): ' + message + '\n'
          break
  return sourceTrace

 
def smackdOutput(corralOutput):
  FILENAME = '[\w#$~%.\/-]+'

  passedMatch = re.search('Program has no bugs', corralOutput)
  if passedMatch:
    json_data = {
      'verifier': 'corral',
      'passed?': True
    }

  else:
    traces = []
    for traceLine in corralOutput.splitlines(True):
      traceMatch = re.match('(' + FILENAME + ')\((\d+),(\d+)\): Trace: Thread=(\d+)  (\((.*)\))?$', traceLine)
      errorMatch = re.match('(' + FILENAME + ')\((\d+),(\d+)\): (error .*)$', traceLine)
      if traceMatch:
        filename = str(traceMatch.group(1))
        lineno = int(traceMatch.group(2))
        colno = int(traceMatch.group(3))
        threadid = int(traceMatch.group(4))
        desc = str(traceMatch.group(6))
        trace = { 'threadid': threadid, 'file': filename, 'line': lineno, 'column': colno, 'description': '' if desc == 'None' else desc }
        traces.append(trace)
      elif errorMatch:
        filename = str(errorMatch.group(1))
        lineno = int(errorMatch.group(2))
        colno = int(errorMatch.group(3))
        desc = str(errorMatch.group(4))
        failsAt = { 'file': filename, 'line': lineno, 'column': colno, 'description': desc }

    json_data = {
      'verifier': 'corral',
      'passed?': False,
      'failsAt': failsAt,
      'threadCount': 1,
      'traces': traces
    }
  json_string = json.dumps(json_data)
  print json_string


if __name__ == '__main__':

  # parse command line arguments
  parser = argparse.ArgumentParser(description='Verifies an SVCOMP benchmark using SMACK.', parents=[smackParser()])
  parser.add_argument('--time-limit', metavar='N', dest='timeLimit', default='1200', type=int,
                      help='Boogie time limit in seconds')
  parser.add_argument('--smackd', dest='smackd', action="store_true", default=False,
                      help='output JSON format for SMACKd')
  parser.add_argument('--outputdir', dest='outputdir', default='./',
                      help='specify the directory where the temporary files are placed')

  args = parser.parse_args() # just check if arguments are looking good

  # remove arguments not recognized by lower scripts
  # not sure of a better way to do this
  sysArgv = sys.argv[:]
  for i in reversed(range(len(sysArgv))):
    if sysArgv[i] == '--smackd':
      del sysArgv[i]
    elif sysArgv[i].endswith('.c') or sysArgv[i].endswith('.i'):
      longfileName = sysArgv[i]
      longfileName = longfileName.split('/')
      shortfileName = path.splitext(longfileName[len(longfileName)-1])[0]

      boogiedirName = args.outputdir+'/BPL_'+longfileName[len(longfileName)-2]+'/'
      cbcdirName = args.outputdir+'/CBC_'+longfileName[len(longfileName)-2]+'/'
      corraldirName = boogiedirName+'/CORRAL_'+shortfileName+'/'

      if(not os.path.exists(boogiedirName)):
        os.system("mkdir "+boogiedirName)
      if(not os.path.exists(cbcdirName)):
        os.system("mkdir "+cbcdirName) 
      if(not os.path.exists(corraldirName)):
        os.system("mkdir "+corraldirName)

      sysArgv[i] = cbcdirName+shortfileName+'.c'

    elif sys.argv[i] == '--time-limit':
      del sysArgv[i]
      del sysArgv[i]

    elif sys.argv[i] == '--outputdir':
      del sysArgv[i]
      del sysArgv[i]

  inputStr = args.infile.read()
  inputStr = '#include "smack.h"\n' + inputStr
  inputStr = inputStr.replace('ERROR:', 'ERROR: __SMACK_assert(0);')
  f = open(cbcdirName+shortfileName+'.c', 'w')
  f.write(inputStr)
  f.close()

  sysArgv = sysArgv + ['--bc'] + [cbcdirName+shortfileName+'.bc'] + ['-o']+ [boogiedirName+shortfileName+'.bpl']


  bpl, options, dummyClangOutput = smackGenerate(sysArgv)#
  args = parser.parse_args(options + sys.argv[1:])

  # write final output
  args.outfile = open(boogiedirName+shortfileName+'.bpl', 'w')
  args.outfile.write(bpl)#
  args.outfile.close()#



  if args.verifier == 'boogie':
    # invoke Boogie
    p = subprocess.Popen(['boogie', args.outfile.name, '/nologo', '/timeLimit:' + str(args.timeLimit), '/loopUnroll:' + str(args.unroll)], stdout=subprocess.PIPE)
    boogieOutput = p.communicate()[0]
    if p.returncode:
      print boogieOutput
      sys.exit("SMACK encountered an error invoking Boogie. Exiting...")
    if args.debug:
      print boogieOutput
    sourceTrace = generateSourceErrorTrace(boogieOutput, bpl)
    if sourceTrace:
      print sourceTrace
    else:
      print boogieOutput
  else:
    # invoke Corral
    os.chdir(corraldirName)
    os.system("cp "+args.outfile.name+" "+shortfileName+'.bpl')
    args.outfile = open(shortfileName+'.bpl',"r")
    p = subprocess.Popen(['corral', args.outfile.name, '/recursionBound:' + str(args.unroll), '/tryCTrace'], stdout=subprocess.PIPE)
    corralOutput = p.communicate()[0]
    if p.returncode:
      print corralOutput
      sys.exit("SMACK encountered an error invoking Corral. Exiting...")
    if args.smackd:
      smackdOutput(corralOutput)
    else:
      print corralOutput

