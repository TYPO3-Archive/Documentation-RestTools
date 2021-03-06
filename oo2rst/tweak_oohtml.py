#! /usr/bin/python
# coding: ascii

"""Tweak an HTML4 file generated by OpenOffice in several ways.

Tags that don't have an end tag will be written as <tag />. Some
endtags are inserted if missing. Some endtags will be removed if
there hasn't been a corresponding opening tag. This tweaker
will try to determine the input encoding and write UTF-8
with BOM = Byte Order Mark on output. An XML declaration is
inserted as first line if not already present.

"""

__version__ = '1.0.3'


# leave your name and notes here:

__history__ = """\

2012-03-08  initial realease
2012-03-09  John Doe  <demo@example.land>
            added: feature ABC
2012-03-11  added: argparse detector
2012-03-11  v1.0.1 ready for git.typo3.org/Documentation/RestTools/oo2rst/
2012-03-16  v1.0.2 Lots of changes! The code is quite a hack in the
            moment - but it works sufficiently.
2012-03-18  used as is for complete conversion process today

"""

__copyright__ = """\

Copyright (c), 2011-2012, Martin Bless  <martin@mbless.de>

All Rights Reserved.

Permission to use, copy, modify, and distribute this software and its
documentation for any purpose and without fee or royalty is hereby
granted, provided that the above copyright notice appears in all copies
and that both that copyright notice and this permission notice appear
in supporting documentation or portions thereof, including
modifications, that you make.

THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO
THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS, IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL,
INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING
FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION
WITH THE USE OR PERFORMANCE OF THIS SOFTWARE!
"""

import codecs
import HTMLParser
import re
import sys

# See:
#   http://www.w3.org/TR/html4/sgml/loosedtd.html
#   http://www.w3.org/TR/html4/index/elements.html

HTML4TAGS_WITH_FORBIDDEN_ENDTAGS = [
    'area', 'base', 'basefont', 'br', 'col', 'frame', 'hr',
    'img', 'input', 'isindex', 'link', 'meta','param']

HTML4TAGS_WITH_OPTIONAL_ENDTAGS = [
    'body', 'colgroup', 'dd', 'dt', 'head', 'html', 'li', 'option',
    'p', 'tbody', 'td', 'tfoot', 'th', 'thead', 'tr']

ALWAYS_CLOSE_ON_NEXT_TAG = ['style', 'script', 'title']

TAGS_TO_BE_SUPPLEMENTED = ['span', 'b', 'i', 'font', 'sdfield']

class MyHTMLParser(HTMLParser.HTMLParser):

    def __init__(self, writer, talk=False):
        HTMLParser.HTMLParser.__init__(self)
        self.w = writer
        self.talk = talk
        self.liststack = []
        self.opentagscounter = {}
        if self.talk:
            sys.stdout.write('\n')
        self.tagstack = []

    def handle_startendtag(self, tag, attrs):
        self.w.write(self.get_starttag_text())

    def closeThisTag(self, tag):
        while self.tagstack and self.tagstack[-1] != tag:
            tag0 = self.tagstack.pop()
            self.w.write('</%s>' % tag0)
            if self.talk:
                sys.stdout.write(' INSERTED: </%s> ' % tag0)
        if self.tagstack and self.tagstack[-1] == tag:
            tag0 = self.tagstack.pop()
            self.w.write('</%s>' % tag0)
        else:
            if self.talk:
                sys.stdout.write('\nOOPS: Iwas told to close tag \'%s\''
                                 '- but that wasn\'t in stack.\n' % tag)

    def handle_starttag(self, tag, attrs):
        log = 0
        s = self.get_starttag_text()

        usestack = True
        if self.tagstack and self.tagstack[-1] in ALWAYS_CLOSE_ON_NEXT_TAG:
            tagtoclose = self.tagstack[-1]
            self.closeThisTag(tagtoclose)
            if self.talk and log:
                sys.stdout.write('</%s> ' % tagtoclose)
        elif (tag in HTML4TAGS_WITH_FORBIDDEN_ENDTAGS and
            s.endswith('>') and not s.endswith('/>')):
            s = s[:-1] + ' />'
            usestack = False
        elif tag in ['li', 'dd', 'dt']:
            log = True
            if len(self.liststack[-1]) > 1:
                tagtoclose = self.liststack[-1].pop()
                self.closeThisTag(tagtoclose)
                if self.talk and log:
                    sys.stdout.write('</%s> ' % tagtoclose)
            self.liststack[-1].append(tag)
        elif tag in ['ol', 'ul', 'dl']:
            self.liststack.append([tag])
            log = True

        if usestack:
            self.tagstack.append(tag)
        self.w.write(s)
        if self.talk and log:
            sys.stdout.write('<%s>' % tag)


    def handle_endtag(self, tag):
        log = 0
        nl = ''
        if tag in ['li']:
            self.liststack[-1].pop()
            log = True

        elif tag in ['ol', 'ul', 'dl'] and len(self.liststack[-1]):
            log = True
            nl = '\n'
            if len(self.liststack[-1]) > 1:
                tagtoclose = self.liststack[-1].pop()
                self.closeThisTag(tagtoclose)
                if self.talk and log:
                    sys.stdout.write('</%s> ' % tagtoclose)
            if len(self.liststack[-1]) > 1:
                'this should not happen'
            self.liststack.pop()

        if tag in TAGS_TO_BE_SUPPLEMENTED:
            if not (self.tagstack and self.tagstack[-1] == tag):
                self.w.write('<%s>' % tag)
                self.tagstack.append(tag)
                if self.talk:
                    sys.stdout.write(' INSERTED: <%s> ' % tag)

        self.closeThisTag(tag)
        if self.talk and log:
            sys.stdout.write('</%s>%s' % (tag, nl))


    def handle_charref(self, name):
        self.w.write('&#%s;' % name)

    def handle_entityref(self, name):
        self.w.write('&%s;' % name)

    def handle_data(self, data):
        self.w.write(data)

    def handle_comment(self, data):
        self.w.write('<!--%s-->' % data )

    def handle_decl(self, decl):
        self.w.write( '<!%s>' % decl)

    def handle_pi(self, data):
        self.error("not yet implemented: handle_pi: %r" % (data,))
        self.w.write(data)

    def unknown_decl(self, data):
        self.error("unknown declaration: %r" % (data,))


def searchFileEncoding(f1name):
    """Check some lines to see if we have an encoding information."""
    f1 = file(f1name)
    cnt = 0
    result = None
    xmlDeclarationFound = False
    maxLinesToCheck = 100
    for line in f1:
        if cnt == 0 and line.startswith('\xef\xbb\xbf'):
            result = 'utf-8'
            break
        line = line.strip().lower()
        if line:
            if line.startswith('<?xml') :
                r = re.search('''encoding\s*=\s*['"](.*)['"]''', line)
                if r:
                    result = r.group(1).strip()
                    if result:
                        xmlDeclarationFound = True
                        break
            elif 'charset' in line:
                # <META HTTP-EQUIV="CONTENT-TYPE" CONTENT="text/html; charset=windows-1252">
                r = re.search('''<meta.*charset=(.*)['"]>''', line)
                if r:
                    result = r.group(1).strip()
                    if result:
                        break
            cnt += 1
            if maxLinesToCheck and cnt > maxLinesToCheck:
                break
    f1.close()
    if result:
        try:
            ' '.encode(result)
        except LookupError:
            result = None
    return result, xmlDeclarationFound



def main(f1name, f2name, talk=False):
    f1encoding, xmlDeclarationFound = searchFileEncoding(f1name)
    if f1encoding is None:
        f1encoding = 'ascii'
    f1 = codecs.open(f1name, 'r', f1encoding)
    f2 = codecs.open(f2name, 'w', 'utf-8-sig')
    if not xmlDeclarationFound:
        f2.write('<?xml version="1.0" encoding="utf-8"?>\n')
    maxlines = None
    P = MyHTMLParser(f2, talk)
    for cnt, line in enumerate(f1):
        P.feed(line)
        if maxlines and (cnt+1) >= maxlines:
            break
    P.close()
    f2.close()



def get_argparse_args():
    """Get commandline args using module 'argparse'. Python >= 2.7 required."""

    class License(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            print __copyright__
            parser.exit()

    class History(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            print __history__
            parser.exit()

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], add_help=False)
    parser.add_argument('--help', '-h', action='help', default=argparse.SUPPRESS, help='show this help message and exit')
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('--license', help='show license', nargs=0, action=License)
    parser.add_argument('--history', help='show history', nargs=0, action=History)
    parser.add_argument('-v', help='verbose - talk to stdout', dest='talk', action='store_true')
    parser.add_argument('infile')
    parser.add_argument('outfile')
    return parser.parse_args()


class Namespace(object):
    """Simple object for storing attributes."""

    def __init__(self, **kwargs):
        for name in kwargs:
            setattr(self, name, kwargs[name])


if __name__=="__main__":

    try:
        import argparse
        argparse_available = True
    except ImportError:
        argparse_available = False

    if argparse_available:
        args = get_argparse_args()
    else:
        args = Namespace()

        # you may hardcode parameters here:
        if 'hardcode parameters here':
            args.infile = ''
            args.outfile = ''
            args.talk = False

        if not args.infile:
            msg = ("\nNote:\n"
                   "   '%(prog)s'\n"
                   "   needs module 'argparse' (Python >= 2.7) to handle commandline\n"
                   "   parameters. It seems that 'argparse' is not available. Provide\n"
                   "   module 'argparse' or hardcode parameters in the code instead.\n" % {'prog': sys.argv[0]} )
            print msg
            sys.exit(2)

    main(args.infile, args.outfile, args.talk)
