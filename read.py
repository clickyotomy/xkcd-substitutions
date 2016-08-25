#! /usr/bin/env python2.7

'''
Substitutions that make reading the news more fun!
Inspired from https://xkcd.com/{1004,1031,1288,1418,1625,1679}/.
'''

import re
import sys
import json
import random
import hashlib
import textwrap
import itertools
from datetime import datetime
from argparse import (ArgumentParser, RawDescriptionHelpFormatter)

import requests
import newspaper

__author__ = 'Srinidhi Kaushik'
__license__ = "MIT"
__version__ = "0.1"
__credits__ = ["ErikR"]


# Load the substitution mappings.
MAPPINGS = json.loads(open('substitutions.json', 'r').read())

# User-Agent string; make it random everytime!
USER_AGENT_STRING = 'bot: xkcd-reddit-substitutions; random: {hash}.'.format

# Reddit Base URL.
URL = 'https://www.reddit.com/r/news/random.json'

# Debug headers.
DEBUG_CALL = '\n[-] {0}\n    {1}'.format

# Metadata.
METADATA = ('posted-by: {user}; on /r/{subreddit} at {time} UTC.\n'
            '\npermalink: {permalink}\ndomain: {domain}.').format


reload(sys)
sys.setdefaultencoding("utf-8")


def replace_with_case(word, replace, text, debug=False):
    '''
    Make a replacement, but preserve the case.
    '''
    def repl(match):
        '''
        Helper sub-module.
        '''
        _text = []
        _group = match.group()
        if debug:
            print '# [repl]: \'{0}\' with \'{1}\'.'.format(_group, replace)

        matches, replaces = _group.split(' '), replace.split(' ')
        for _match, _replacement in itertools.izip_longest(matches, replaces):
            if _match is not None:
                if _match.isupper():
                    _text.append(_replacement.upper())
                elif _match.islower():
                    _text.append(_replacement.lower())
                elif _match.istitle():
                    _text.append(_replacement.title())
                else:
                    _text.append(_replacement)
            else:
                _text.append(_replacement)

        return ' '.join(_text)
    return re.sub(r'\b{0}\b'.format(word), repl, text, flags=re.IGNORECASE)


def justify(text, length=70):
    '''
    Justify text for a given width.
    '''
    sentences = []
    words = text.split()
    try:
        if len(max(words, key=len)) > length:
            return []
    except ValueError:
        return []

    groups, index = [], 0
    while index < len(words):
        group_length, group = 0, []
        while index < len(words):
            if group_length <= length:
                if len(words[index]) < length:
                    group_length += (len(words[index]) + 1)
                else:
                    group_length += len(words[index])
                group.append(words[index])
                index += 1
            else:
                group.pop()
                index -= 1
                break
        if index >= len(words) and group_length > length:
            groups.append(group[:-1])
            groups.append([group[-1]])
        else:
            groups.append(group)

    for group in groups[:-1]:
        slots = len(group) - 1
        spaces = length - sum(len(word) for word in group)
        if not spaces:
            sentences.append([group])
        elif len(group) == 1 and spaces:
            sentences.append([group[0].ljust(length, ' ')])
        else:
            possible = [_ for _ in list(rule_asc_len(spaces, slots))
                        if (len(_) + 1) == len(group)]
            index = len(possible)
            spaces = [] if not len(possible) else possible[-1]
            spaces = [' ' * _ for _ in spaces]
            together = [item for sublist in map(None, group, spaces)
                        for item in sublist][:-1]
            sentences.append(together)
    sentences.append([' '.join(groups[-1]).ljust(length, ' ')])
    return sentences


def rule_asc_len(number, limit):
    '''
    Integer Partitions: http://math.stackexchange.com/questions/18659/.
    This is a helper module for justify().
    '''
    array = [0 for _ in range(number + 1)]
    index = 1
    array[0] = 0
    array[1] = number
    while index != 0:
        _prev = array[index - 1] + 1
        _next = array[index] - 1
        index -= 1
        while _prev <= _next and index < (limit - 1):
            array[index] = _prev
            _next -= _prev
            index += 1
        array[index] = _prev + _next
        yield array[:index + 1]


def http_debug(response):
    '''
    Print the HTTP request/response debug log.
    '''
    print 'http-request\n{0}\n'.format('-' * len('http-request'))
    print 'url ({0}): {1}'.format(response.request.method,
                                  response.request.url)
    print 'request-headers:'
    print json.dumps(dict(response.request.headers), indent=4)
    if response.request.method != 'GET':
        print 'request-payload:'
        print json.dumps(json.loads(response.request.body), indent=4)
    print '\nhttp-response\n{0}\n'.format('-' * len('http-response'))
    print 'status-code: {0} {1}'.format(response.status_code, response.reason)
    print 'url: {0}'.format(response.url)
    print 'time-elapsed: {0}s'.format(response.elapsed.total_seconds())
    print 'response-headers:'
    print json.dumps(dict(response.headers), indent=4)
    print 'response-content:'
    print None if response.content is '' else json.dumps(response.json(),
                                                         indent=4)


def reddit(debug=False):
    '''
    Fetch a random post from Reddit (http://www.reddit.com/r/news).
    '''
    _hash = hashlib.sha1(str(random.random())).hexdigest()
    headers = {
        'User-Agent': USER_AGENT_STRING(hash=_hash)
    }

    content = None
    flag = False
    retries = 0

    while not flag and retries < 5:
        try:
            post = requests.get(URL, headers=headers, allow_redirects=True)
            if debug:
                print DEBUG_CALL('news-random-call',
                                 '-' * len('news-random-call'))
                http_debug(post)
            if post.status_code >= 200 and post.status_code < 400:
                data = post.json()[0]['data']['children'][0]
                url = data['data']['url'] if len(data['data']['url']) > 0\
                    else None
                content = {
                    'url': url,
                    'domain': data['data']['domain'],
                    'subreddit': data['data']['subreddit'],
                    'permalink': data['data']['permalink'],
                    'time': int(data['data']['created_utc']),
                    'reddit-author': data['data']['author']
                }
                flag = True if url is not None else False

            retries += 1

        except requests.exceptions.RequestException as http_error:
            print http_error[0][0]
            print "Fetching another article (retries: {0}).".format(retries)
            continue
        except (ValueError, KeyError, IndexError):
            print 'Unable to parse response from Reddit.'
            print "Fetching another article (retries: {0}).".format(retries)
            continue

    return content


def fetch(width=70, text_debug=False, request_debug=False, repl_debug=False):
    '''
    Fetch the article using 'newspaper'.
    '''
    post = reddit(request_debug)
    if post is None:
        return

    article = newspaper.Article(post['url'])
    time = datetime.fromtimestamp(post['time']).strftime('%Y-%m-%d %H:%M:%S')

    article.download()
    article.parse()

    text = re.sub(r'\n+', '\n', article.text)

    # Print the source metadata.
    print '\n{0}\n'.format('*' * width)
    print textwrap.fill(('# posted-by: {user}; on /r/{subreddit} at {time} UTC'
                         ' (reddit.com).').format(user=post['reddit-author'],
                                                  subreddit=post['subreddit'],
                                                  time=time),
                        subsequent_indent=' ' * 13, width=width)
    print textwrap.fill('# permalink: http://www.reddit.com{permalink}'.format(
        permalink=post['permalink']), subsequent_indent=' ' * 13, width=width)
    print textwrap.fill('# domain:    {domain}'.format(domain=post['domain']),
                        subsequent_indent=' ' * 13, width=width)

    print textwrap.fill('# source:    {url}'.format(url=post['url']),
                        subsequent_indent=' ' * 13, width=width)
    print '\n{0}\n'.format('*' * width)

    # Display raw data from the news article.
    if text_debug:
        print '\n{0}\n'.format('~' * width)
        print DEBUG_CALL('original-content', '-' * len('original-content'))
        print '\n'.join([_.center(width, ' ') for _ in
                         textwrap.wrap(article.title, width=width)])
        justified = justify(text, width)
        print '\n'
        for sentence in justified:
            print ''.join(sentence)

        print '\n{0}\n'.format('~' * width)

    # Parse the content, justify and display the text.
    print '\n'.join([_.center(width, ' ') for _ in
                     textwrap.wrap(substitute(article.title, repl_debug),
                                   width=width)])
    print '\n{0}\n'.format('-' * width)

    for sentence in text.split('\n'):
        substituted = justify(substitute(sentence, repl_debug), width)
        for sentence in substituted:
            print ''.join(sentence)
        print ''
    print '{0}\n'.format('^' * width)


def substitute(content, repl_debug):
    '''
    Make the substitution.
    '''
    for _word, _substitute in MAPPINGS.iteritems():
        content = replace_with_case(_word, _substitute, content, repl_debug)

    return content


def main():
    '''
    Validate arguments, display content.
    '''
    message = ('Substitutions that make reading the news more fun!\n'
               'https://github.com/clickyotomy/xkcd-substitutions')

    debug_help = ('enable debugging; http: http-requests, '
                  'text: orignal-content, repl: text-replacement')
    parser = ArgumentParser(description=message,
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('-w', '--width', help='text width; default: 80',
                        default=80, type=int, metavar=('N'))
    parser.add_argument('-d', '--debug', help=debug_help, default=[],
                        nargs='*', choices=('http', 'text', 'repl'),
                        metavar=('DEBUG', 'http, text, repl'))
    args = vars(parser.parse_args())

    debug_args = {
        'text_debug': False,
        'request_debug': False
    }

    if 'http' in args['debug']:
        debug_args.update({'request_debug': True})

    if 'text' in args['debug']:
        debug_args.update({'text_debug': True})

    if 'repl' in args['debug']:
        debug_args.update({'repl_debug': True})

    fetch(width=args['width'], **debug_args)

if __name__ == '__main__':
    main()
