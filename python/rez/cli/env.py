'''
Invoke a shell based on a configuration request.
'''

import argparse
import sys
import os

# _g_usage = "rez-env [options] pkg1 pkg2 ... pkgN"


# class OptionParser2(optparse.OptionParser):
#     def exit(self, status=0, msg=None):
#         if msg:
#             sys.stderr.write(msg)
#         sys.exit(1)


def setup_parser(parser):
    # settings shared with rez-config
    parser.add_argument("pkg", nargs='+',
                        help='list of package names')
    parser.add_argument("-m", "--mode", dest="mode", type=str, default="latest",
                        help="Set the package resolution mode [default=%(default)s]")
    parser.add_argument("-q", "--quiet", dest="quiet",
                        action="store_true", default=False,
                        help="Suppress unnecessary output [default = %(default)s]")
    parser.add_argument("-o", "--no-os", "--no_os", dest="no_os",
                        action="store_true", default=False,
                        help="Stop rez-env from implicitly requesting the operating system package [default = %(default)s]")
    parser.add_argument("-b", "--build", "--build-requires", dest="buildreqs",
                        action="store_true", default=False,
                        help="Include build-only package requirements [default = %(default)s]")
    parser.add_argument("--no-cache", dest="no_cache",
                        action="store_true", default=False,
                        help="disable caching [default = %(default)s]")
    parser.add_argument("-g", "--ignore_archiving", dest="ignore_archiving",
                        action="store_true", default=False,
                        help="Include archived packages [default = %(default)s]")
    parser.add_argument("-u", "--ignore-blacklist", "--ignore_blacklist", dest="ignore_blacklist",
                        action="store_true", default=False,
                        help="Include blacklisted packages [default = %(default)s]")
    parser.add_argument("-d", "--no-assume-dt", "--no_assume_dt", dest="no_assume_dt",
                        action="store_true", default=False,
                        help="Do not assume dependency transitivity [default = %(default)s]")
    parser.add_argument("-i", "--time", dest="time", type=int,
                        default=0,
                        help="Ignore packages newer than the given epoch time")
    parser.add_argument("--no-local", dest="no_local",
                        action="store_true", default=False,
                        help="don't load local packages")

    parser.add_argument("-p", "--prompt", dest="prompt", type=str,
                        default=">",
                        help="Set the prompt decorator [default=%(default)s]")
    parser.add_argument("-r", "--rcfile", dest="rcfile", type=str,
                        default='',
                        help="Source this file after the new shell is invoked")
    parser.add_argument("--tmpdir", dest="tmpdir", type=str,
                        default=None,
                        help="Set the temp directory manually, /tmp otherwise")
    parser.add_argument("--propogate-rcfile", dest="prop_rcfile",
                        action="store_true", default=False,
                        help="Propogate rcfile into subshells")
    parser.add_argument("-s", "--stdin", dest="stdin",
                        action="store_true", default=False,
                        help="Read commands from stdin, rather than starting an interactive shell [default = %(default)s]")
    parser.add_argument("-a", "--add-loose", "--add_loose", dest="add_loose",
                        action="store_true", default=False,
                        help="Add mode (loose). Packages will override or add to the existing request list [default = %(default)s]")
    parser.add_argument("-t", "--add-strict", "--add_strict", dest="add_strict",
                        action="store_true", default=False,
                        help="Add mode (strict). Packages will override or add to the existing resolve list [default = %(default)s]")
    parser.add_argument("-f", "--view-fail", "--view_fail", dest="view_fail", type=int,
                        default=-1,
                        help="View the dotgraph for the Nth failed config attempt")

def _autowrappers(pkglist):
    return any([pkg for pkg in pkglist if '(' in pkg])

def command(opts):
    import tempfile
    autowrappers = _autowrappers(opts.pkg)
    raw_request = os.getenv('REZ_RAW_REQUEST', '')
    if opts.add_loose or opts.add_strict:
        if autowrappers:
            sys.stdout.write("Patching of auto-wrapper environments is not yet supported.\n")
            sys.exit(1)

        if _autowrappers(raw_request.split()):
            sys.stdout.write("Patching from auto-wrapper environments is not yet supported.\n")
            sys.exit(1)

    ##############################################################################
    # switch to auto-wrapper rez-env if bracket syntax is detected
    # TODO patching of wrapper envs is not yet supported.
    ##############################################################################
    if autowrappers:
        if not opts.tmpdir:
            opts.tmpdir = tempfile.mkdtemp()

        os.environ['REZ_TMP_DIR'] = opts.tmpdir

        import rez.cli.env_autowrappers
        rez.cli.env_autowrappers.command(opts)

        os.environ['REZ_PACKAGES_PATH'] = opts.tmpdir + ':' + os.environ['REZ_PACKAGES_PATH']
        packages_file = os.path.join(opts.tmpdir, 'packages.txt')
        with open(packages_file, 'r') as f:
            packages = f.read()
#         unset _REZ_ENV_OPT_ADD_LOOSE
#         unset _REZ_ENV_OPT_ADD_STRICT
        opts.no_cache = True
    else:
        packages = ' '.join(opts.pkg)

    ##############################################################################
    # apply patching, if any
    ##############################################################################

    if opts.add_loose:
        ctxt_pkg_list = os.environ['REZ_REQUEST']
        print_pkgs = True
    elif opts.add_strict:
        ctxt_pkg_list = os.environ['REZ_RESOLVE']
        print_pkgs = True
    else:
        ctxt_pkg_list = None
        print_pkgs = False

    if not ctxt_pkg_list:
        pkg_list = packages
    else:
        import rez.rez_parse_request as rpr
        base_pkgs, subshells = rpr.parse_request(ctxt_pkg_list + " | " + packages)
        pkg_list = rpr.encode_request(base_pkgs, subshells)

    if print_pkgs and not opts.quiet:
        quotedpkgs = ["'%s'" % pkg for pkg in pkg_list.split()]
        print>>sys.stderr, "request: %s" % ' '.join(quotedpkgs)


    ##############################################################################
    # call rez-config, and write env into bake file
    ##############################################################################

    tmpf = tempfile.mktemp(dir=opts.tmpdir, prefix='.rez-context.')
    tmpf2 = tmpf + ".source"
    tmpf3 = tmpf + ".dot"

    from . import config as rez_cli_config

    kwargs = vars(opts)
    kwargs['quiet'] = True
    # TODO: provide a util which reads defaults for the cli command
    config_opts = argparse.Namespace(verbosity=0,
                                     version=False,
                                     print_env=False,
                                     print_dot=False,
                                     meta_info='tools',
                                     meta_info_shallow='tools',
                                     env_file=tmpf,
                                     dot_file=tmpf3,
                                     max_fails=opts.view_fail,
                                     wrapper=False,
                                     no_catch=False,
                                     no_path_append=False,
                                     print_pkgs=False,
                                     **kwargs)
    try:
#         rez-config
#         --time=$_REZ_ENV_OPT_TIME
#         --print-env
#         --meta-info=tools
#         --meta-info-shallow=tools
#         --dot-file=$tmpf3
#         --mode=$_REZ_ENV_OPT_MODE
#         $max_fails_flag $dt_flag $ignore_archiving_flag $use_blacklist_flag $buildreq_flag $no_os_flag $no_local_flag $no_cache_flag $pkg_list > $tmpf
        rez_cli_config.command(config_opts)
        # capture output into: $tmpf
    except Exception, err:
        print>>sys.stderr, err
        try:
            # TODO: change cli convention so that commands do not call sys.exit
            # and we can actually catch this exception
            if opts.view_fail != "-1":
                from . import dot as rez_cli_dot
                dot_opts = argparse.Namespace(conflict_only=True,
                                              package="",
                                              dotfile=tmpf3)
                rez_cli_dot.command(dot_opts)
            sys.exit(1)
        finally:
            if os.path.exists(tmpf):
                os.remove(tmpf)
            if os.path.exists(tmpf3):
                os.remove(tmpf3)

    if autowrappers:
        with open(tmpf, 'w') as f:
            f.write("export REZ_RAW_REQUEST='%s'\n" % packages)

    ##############################################################################
    # spawn the new shell, sourcing the bake file
    ##############################################################################

    if not raw_request:
        print "export REZ_RAW_REQUEST='%s';" % packages

    print "export REZ_CONTEXT_FILE=%s;" % tmpf
    print 'export REZ_ENV_PROMPT="%s";' % (os.getenv('REZ_ENV_PROMPT', '') + opts.prompt)
 
    if opts.stdin:
        print "source %s;" % tmpf
        if not opts.rcfile:
            if os.path.exists(os.path.expanduser('~/.bashrc')):
                print "source ~/.bashrc &> /dev/null;"
        else:
            print "source %s;" % opts.rcfile
#                 if [ $? -ne 0 ]; then
#                     exit 1
#                 fi
 
        # ensure that rez-config is available no matter what (eg .bashrc might not exist,
        # rcfile might not source rez-config)
        print "source $REZ_PATH/init.sh;"
        print "bash -s;"
        print "ret=$?;"
    else:
        with open(tmpf2, 'w') as f:
            f.write("source %s\n" % tmpf)
            if opts.rcfile:
                f.write("source %s\n" % opts.rcfile)

            f.write("source rez-env-bashrc\n")
            if not opts.quiet:
                f.write("echo\n")
                f.write("echo You are now in a new environment.\n")
                f.write("rez-context-info\n")
 
        print "bash --rcfile %s;" % tmpf2
        print "ret=$?;"
        print "rm -f %s;" % tmpf2

    print "rm -f %s;" % tmpf
    print "rm -f %s;" % tmpf3
    #print "exit $ret;"


#    Copyright 2008-2012 Dr D Studios Pty Limited (ACN 127 184 954) (Dr. D Studios)
#
#    This file is part of Rez.
#
#    Rez is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Rez is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Rez.  If not, see <http://www.gnu.org/licenses/>.
