#!/usr/bin/env python3
from __future__ import print_function
import os
import sys
import fcntl  # (file locking)
import contextlib
import tempfile
import shutil
import itertools
from io import open
import codecs
import argparse


@contextlib.contextmanager
def interprocess_lock(lock_file):
    with open(lock_file, "a+") as f:
        fcntl.lockf(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.lockf(f, fcntl.LOCK_UN)


@contextlib.contextmanager
def save_replace(filename, *a, **kw):
    with tempfile.NamedTemporaryFile(*a, **kw) as file_like:
        yield file_like
        file_like.flush()
        shutil.copy(file_like.name, filename)


def do_the_magic(historyfile, append_filename, backupfile):
    backup = os.path.expanduser(backupfile)
    if not os.path.exists(historyfile):
        print("historyfile: %s does not exist" % (historyfile,))
        sys.exit(1)

    # read the old history
    with open(historyfile, "r+", encoding="utf8", errors="ignore") as f:
        fcntl.lockf(f, fcntl.LOCK_EX)
        history_lines = f.readlines()
        history_lines.reverse()  # newest first
        print("Uniquehist %d" % (len(history_lines),))

        if append_filename and os.path.exists(append_filename):
            assert "tmp" in append_filename
            with open(append_filename, "r+", encoding="utf8", errors="ignore") as addfile:
                additionlines = addfile.readlines()
                additionlines.reverse()
                history_lines = additionlines + history_lines
            os.unlink(append_filename)

        short = []
        setcheck = {}
        # keep only the newest unique entry
        for s in history_lines:
            val = s.rstrip()
            if val not in setcheck:
                short.append(val)
                setcheck[val] = True

        short.reverse()  # and put in proper order again
        if os.path.getsize(backup) < os.path.getsize(historyfile) + 80:
            with save_replace(backup, "w") as f_bkp:
                for s in short:
                    f_bkp.write(s + "\n")
        else:
            sys.stdout.write(
                "ERROR: history file is smaller than backup; Try appending the backup file (%s) to the history file or uniquifying the backup file.\n"
                % (backupfile,)
            )

    with save_replace(historyfile, "w") as f_out:
        for s in short:
            f_out.write("%s\n" % (s,))


def install(history_file):
    ENV = os.environ
    default_histsize = 200_000
    histsize = max(ENV.get("HISTSIZE", default_histsize), default_histsize)

    sourceable = """
    export HISTCONTROL=ignoreboth  # ignore commands with leading whitespace.
    export UNIQUEHIST_FILE={history_file}
    export UNIQUEHIST_APPEND_FILE=$(mktemp --suffix="bash-$$.uniquehist")
    export UNIQUEHIST_COMMAND="history -a $UNIQUEHIST_APPEND_FILE; uniquehist -H $UNIQUEHIST_FILE -A $UNIQUEHIST_APPEND_FILE; history -c ; history -r $UNIQUEHIST_FILE"
    if echo $PROMPT_COMMAND |grep uniquehist 1>/dev/null 2>&1; then
        echo "uniquehist already installed"
    else
        export PROMPT_COMMAND="${{PROMPT_COMMAND:+$PROMPT_COMMAND ;}} ${{UNIQUEHIST_COMMAND}}"
        echo "installing uniquehist"
    fi
    """.format(
        history_file=history_file
    )
    print(sourceable)


def main():
    parser = argparse.ArgumentParser(description="Process history and append files")

    parser.add_argument(
        "-H",
        "--history_file",
        metavar="history_file",
        help="Path to the history file",
        default="$HOME/.unique_bash_history",
    )
    parser.add_argument("-A", "--append_file", metavar="append_file", nargs="?", help="Path to the append file")
    parser.add_argument("-B", "--backup_file", metavar="backup_file", nargs="?", help="Path to the backup file")

    parser.add_argument("--lock-file", dest="lock_file", help="Path to the lock file", default=None)
    parser.add_argument("--install", action="store_true", help="""Output the code for installing the prompt command.

    use this command to install uniquehist:

    source <(uniquehist --install)
    """)
    parser.add_argument(
        "--install-if-required",
        action="store_true",
        help="Output the code for installing the prompt command, if it's not present in the prompt command.",
    )

    args = parser.parse_args()

    if args.install:
        install(args.history_file)
    else:
        historyfile = args.history_file
        append_filename = args.append_file
        backup_file = args.backup_file or os.path.join(historyfile, "1.bkp")
        # probably bad to use the history file as backup because save_replace removes it....
        lock_file = args.lock_file or "%s.lock" % (historyfile,)

        with interprocess_lock(lock_file):
            do_the_magic(historyfile=historyfile, append_filename=append_filename, backupfile=backupfile)


if __name__ == "__main__":
    main()
