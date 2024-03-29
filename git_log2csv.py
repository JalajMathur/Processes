#!/usr/bin/env python

# gitjson - git wrapper for JSON output
#
# Run 'gitjson --help' for usage.
#
# Copyright 2014 Paul Rademacher
# Released under the MIT license

import json
import subprocess
import sys

USAGE = '''
 Usage:
    gitjson [standard git options] <git-command> [--json=<flags>]
            [standard git command options]

 git-command must be 'log' or 'shortlog'.

 For 'log' command:
     You can restrict the fields to include in the JSON response with
     '--json=flags'.  The following flags are supported:

        a : author name
        e : author email
        h : sha
        d : date
        s : subject/title
        f : file list
        p : list of parent hashes
        t : tree hash
'''

def usage():
    print (USAGE)


# Remove one or more elements from an list of strings, matching on prefix.
# strings_to_remove can be a single string or a list of strings.
def remove_elements(string_list, strings_to_remove):
    if isinstance(strings_to_remove, str):
        removals = [strings_to_remove]
    else:
        removals = strings_to_remove

    out = []
    for el in string_list:
        for removal in removals:
            if el.startswith(removal):
                break
        else:
            out.append(el)

    return out


# Check if the args contain a 1-char flag.
def has_flag(all_args, flag_to_check):
    for arg in all_args:
        if arg[0] == '-' and arg[1] != '-':  # Must be single-dash flag.
            if flag_to_check in arg:
                return True
    return False


# Take a string of 1-char flags, and compare it to a string of allowed flags.
# If any don't match, display an error and exit.
def check_flags(incoming_flags, allowed_flags, error_message):
    has_error = False
    for incoming_flag in incoming_flags:
        if not incoming_flag in allowed_flags:
            sys.stderr.write('%s: "%c"\n' % (error_message, incoming_flag))
            has_error = True
    if has_error:
        sys.exit(-2)


# Run git log, passing along the original command-line arguments (as 'args').
def git_shortlog(args, json_flags):
    summary_flag = has_flag(args, 's')
    numbered_flag = has_flag(args, 'n')
    email_flag = has_flag(args, 'e')

    output = subprocess.check_output(['git'] + args)
    lines = output.split('\n')

    author_entries = []
    if summary_flag:
        # One line per author.
        for line in lines:
            line = line.strip()
            fields = line.split('\t')
            if len(fields) > 1:
                count = int(fields[0])
                author = " ".join(fields[1:])
                if email_flag:
                    fields = author.split('<')
                    if len(fields) == 2:
                        name = fields[0].strip()
                        email = fields[1].strip()[:-1]
                        author_entries.append({'name': name, 'email': email,
                                               'count': count})
                else:
                    author_entries.append({'name': author, 'count': count})
    else:
        pass

    print (json.dumps(author_entries))


# Run git log, passing along the original command-line arguments (as 'args').
def git_log(args, json_flags):
    # If json_flags is not empty string, then the presence of the following characters
    # determines whether a data field is included in the output.  See usage() for allowed
    # flags.

    check_flags(json_flags, 'aehdsfpt', 'Unrecognized flag')

    # Remove any formatting arguments, since we must use our own
    # formatting in order to parse properly.
    args = remove_elements(args, ['--oneline', '--pretty', '--parents',
                                  '--children', '--graph', '--notes',
                                  '--show_notes'])

    START_OF_COMMIT = '@@@@@@@@@@'

    args += ['--pretty=tformat:' + START_OF_COMMIT + '%n%h%n%aN%n%aE%n%at%n%ai%n%p%n%t%n%s',
             '--date=local',
             '--numstat']

    try:
        # output = subprocess.check_output(['git'] + args)
        # output = subprocess.run(['git'] + args, stdout=subprocess.PIPE).stdout.decode('utf-8')
        # output = subprocess.getoutput(" ".join(['git'] + args))
        output = subprocess.getoutput("git log --pretty=tformat:@@@@@@@@@@%n%h%n%aN%n%aE%n%at%n%ai%n%p%n%t%n%s --date=local --numstat")
    except Exception as e:
        print (e)

    # Step through output, parsing each commit.
    commits = []
    lines = output.split('\n')

    i = 0
    while i < len(lines):
        if not lines[i]:
            # End of log.
            break

        i += 1  # Skip the START_OF_COMMIT marker.

        sha = lines[i]
        name = lines[i+1]
        email = lines[i+2]
        date = lines[i+3]
        date_iso = lines[i+4]
        parents = lines[i+5].split(' ')
        tree = lines[i+6]
        subject = lines[i+7]
        i += 8

        files = []

        # If there is a numstat, process it.
        if lines[i] != START_OF_COMMIT:
            i += 1  # Skip blank line before numstat.

            # Read the numstat.
            while i < len(lines) and lines[i] and \
                    (lines[i][0].isdigit() or lines[i][0] == '-'):
                fields = lines[i].split('\t')
                files.append({'ins': fields[0], 'del': fields[1], 'path': fields[2]})
                i += 1

        commit = {}
        if not json_flags or 'h' in json_flags:
            commit['sha'] = sha
        if not json_flags or 'a' in json_flags:
            commit['name'] = name
        if not json_flags or 'e' in json_flags:
            commit['email'] = email
        if not json_flags or 'd' in json_flags:
            commit['date'] = date
            commit['date_iso'] = date_iso
        if not json_flags or 's' in json_flags:
            commit['subject'] = subject
        if not json_flags or 'f' in json_flags:
            commit['files'] = files
        if not json_flags or 'p' in json_flags:
            commit['parents'] = parents
        if not json_flags or 't' in json_flags:
            commit['tree'] = tree

        commits.append(commit)
    #write json file to disk, log.json
    # json.dump(commits, open('log.json', 'w'), indent=4)
    import pandas as pd
    df = pd.json_normalize(commits, record_path=['files'], meta=['name', 'date_iso', 'subject', 'sha'])
    df.to_csv('log.csv')


if __name__ == '__main__':
    args = sys.argv

    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        usage()
        sys.exit(0)

    # Find the git command name, which is the first argument not prefixed with
    # a dash, and not containing an equal sign.
    command = 'log'
    for arg in args[1:]:
        if not arg.startswith('-') and arg.find('=') == -1:
            # This is the git command name.
            if arg != 'log' and arg != 'shortlog':
                sys.stderr.write('Only "log" and "shortlog" are supported\n')
                sys.exit(-1)
            else:
                command = arg
                break

    # Look for --json=xyz flag.
    json_flags = ''
    for arg in args[1:]:
        if arg.startswith('--json='):
            json_flags = arg[7:]

    # Remove the --json=xyz flag so it doesn't get passed to the underlying git
    # command.
    args = remove_elements(args, '--json=')

    if not command:
        sys.stderr.write('Git command must be specified (2nd parameter)\n')
        sys.exit(-2)

    if command == 'log':
        git_log(args[1:], json_flags)
    elif command == 'shortlog':
        git_shortlog(args[1:], json_flags)
