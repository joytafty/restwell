#!/usr/bin/env python

import argparse
import datetime
import fitbit
from flask import Flask, url_for, render_template
from functools import update_wrapper
from jinja2 import Environment, FileSystemLoader
import json
import os
import redis
import time
import urlparse

# Local
redis = redis.Redis()

def crossdomain(origin=None, methods=None, headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True):
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, basestring):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, basestring):
        origin = ', '.join(origin)
    if isinstance(max_age, datetime.timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator

def load():

    # see: http://python-fitbit.readthedocs.org/en/latest/#fitbit-api
    fb = fitbit.Fitbit(
        os.getenv('CONSUMER_KEY'),
        os.getenv('CONSUMER_SECRET'), 
        user_key=os.getenv('USER_KEY'),
        user_secret=os.getenv('USER_SECRET'))
    
    redis.delete('fitbit')
    
    if True:
        sleepData = dict();
        sl1 = fb.time_series('sleep/startTime', period='max')['sleep-startTime']
        sl2 = fb.time_series('sleep/timeInBed', period='max')['sleep-timeInBed']
        sl3 = fb.time_series('sleep/minutesAsleep', period='max')['sleep-minutesAsleep']
        sl4 = fb.time_series('sleep/minutesAwake', period='max')['sleep-minutesAwake']
        sl5 = fb.time_series('sleep/minutesToFallAsleep', period='max')['sleep-minutesToFallAsleep']
        sl6 = fb.time_series('sleep/minutesAfterWakeup', period='max')['sleep-minutesAfterWakeup']
        sl7 = fb.time_series('sleep/efficiency', period='max')['sleep-efficiency']
        
        for sl in range(len(sl1)):            
            if sl1[sl]['value'] != '':                
                sleepData['date'] = sl1[sl]['dateTime']
                sleepData['startTime'] = sl1[sl]['value']
                sleepData['timeInBed'] = sl2[sl]['value']
                sleepData['minutesAsleep'] = sl3[sl]['value']
                sleepData['minutesAwake'] = sl4[sl]['value']
                sleepData['minutesToFallAsleep'] = sl5[sl]['value']
                sleepData['minutesAfterWakeup'] = sl6[sl]['value']
                sleepData['efficiency'] = sl7[sl]['value']
                sleepData['timezone'] = fb.user_profile_get()['user']['timezone']
                sleepData['offsetFromUTCMillis'] = fb.user_profile_get()['user']['offsetFromUTCMillis']
                s = json.dumps(sleepData)
                redis.sadd('fitbit', s)
                print s



def old_auth():
    pass
    import oauth2 as oauth
    import urllib2
    import urlparse
    consumer = oauth.Consumer(
        key    = 'e83cb29ae0f0439e8aeb2704b5e9eaa4',
        secret = '77fdd761c63247868627cc4ed2114306')

    client = oauth.Client(consumer)
    # resp, content = client.request('https://api.fitbit.com/oauth/request_token')    
    resp, content = client.request('https://api.fitbit.com/oauth/request_token', force_auth_header=True)
    if resp['status'] != '200':
        raise Exception("Invalid response %s." % resp['status'])

    request_token = dict(urlparse.parse_qsl(content))

    print "Request Token:"
    print "    - oauth_token        = %s" % request_token['oauth_token']
    print "    - oauth_token_secret = %s" % request_token['oauth_token_secret']
    print 

    print "Go to the following link in your browser:"
    print "%s?oauth_token=%s" % (
        'https://www.fitbit.com/oauth/authorize', 
        request_token['oauth_token'])
    print 

    accepted = 'n'
    while accepted.lower() == 'n':
        accepted = raw_input('Have you authorized me? (y/n) ')
    oauth_verifier = raw_input('What is the PIN? ')

    token = oauth.Token(
        request_token['oauth_token'],
        request_token['oauth_token_secret'])
    token.set_verifier(oauth_verifier)

    client = oauth.Client(consumer, token)
    resp, content = client.request(
        'https://api.fitbit.com/oauth/access_token', 
        "POST")
    access_token = dict(urlparse.parse_qsl(content))

    print "Access Token:"
    print "    - oauth_token        = %s" % access_token['oauth_token']
    print "    - oauth_token_secret = %s" % access_token['oauth_token_secret']
    print
    print "You may now access protected resources using the access tokens above." 
    print

def server():
    from cherrypy import wsgiserver
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static'))
    # app = Flask(__name__)

    @app.route('/data.json')
    # @crossdomain(origin='*')
    def data_json():
        s = json.dumps([json.loads(s) for s in 
            list(redis.smembers('fitbit'))])
        return s

    @app.route('/sleep/sleepRecord.json')
    def sleep_json():
        fb = fitbit.Fitbit(os.getenv('FITBIT_KEY'), os.getenv('FITBIT_SECRET'), 
            user_key=flask.session['FITBIT_TOKEN'], user_secret=flask.session['FITBIT_TOKEN_SECRET'])
        startTime = fb.time_series('sleep/startTime', period='max')
        timeInBed = fb.time_series('sleep/timeInBed', period='max')
        minutesAsleep = fb.time_series('sleep/minutesAsleep', period='max')
        minutesAwake = fb.time_series('sleep/minutesAwake', period='max')
        minutesAfterWakeup = fb.time_series('sleep/minutesAfterWakeup', period='max')
        minutesToFallAsleep = fb.time_series('sleep/minutesToFallAsleep', period='max')
        efficiency = fb.time_series('sleep/efficiency', period='max')

        data = {
            # only show if value != ''
            'sleep-startTime': [datum for datum in startTime['sleep-startTime'] if datum['value']],
            'sleep-timeInBed': [datum for datum in timeInBed['sleep-timeInBed'] if datum['value'] != '0'],
            'sleep-minutesAsleep': [datum for datum in minutesAsleep['sleep-minutesAsleep'] if datum['value'] != '0'],
            'sleep-minutesAwake': [datum for datum in minutesAwake['sleep-minutesAwake'] if datum['value'] != '0'],
            'sleep-minutesAfterWakeup': [datum for datum in minutesAfterWakeup['sleep-minutesAfterWakeup'] if datum['value'] != '0'],
            'sleep-minutesToFallAsleep': [datum for datum in minutesToFallAsleep['sleep-minutesToFallAsleep'] if datum['value'] != '0'],
            'sleep-efficiency': [datum for datum in efficiency['sleep-efficiency'] if datum['value'] != '0'],
        }
        return json.dumps(data)
    
    @app.route('/')
    def index_html():
        context = {
            'fitbit_authenticated': 'FITBIT_TOKEN' in flask.session,
        }
        env = Environment(loader=FileSystemLoader('templates'))
        return env.get_template('index.html').render(context)
    
    @app.route('/logout')
    def logout():
        del flask.session['FITBIT_TOKEN']
        del flask.session['FITBIT_TOKEN_SECRET']
        return flask.redirect('https://www.fitbit.com/logout')
    
    @app.route('/login')
    def login():
        import urllib2
    
        consumer = oauth.Consumer(os.getenv('FITBIT_KEY'), os.getenv('FITBIT_SECRET'))
        client = oauth.Client(consumer)
        resp, content = client.request('https://api.fitbit.com/oauth/request_token')    
        # resp, content = client.request('https://api.fitbit.com/oauth/request_token', force_auth_header=True)
        if resp['status'] != '200':
            raise Exception("Invalid response %s." % resp['status'])

        request_token = dict(urlparse.parse_qsl(content))

        url = 'https://www.fitbit.com/oauth/authenticate?oauth_token=' + request_token['oauth_token']
        return flask.redirect(url)
        
    @app.route('/fitbit')
    def fitbit_callback():
        consumer = oauth.Consumer(os.getenv('FITBIT_KEY'), os.getenv('FITBIT_SECRET'))
        token = oauth.Token(flask.request.args.get('oauth_token'), flask.request.args.get('oauth_verifier'))
        token.set_verifier(flask.request.args.get('oauth_verifier'))
        client = oauth.Client(consumer, token)
        resp, content = client.request('https://api.fitbit.com/oauth/access_token', 'POST')
        if resp['status'] != '200':
            raise Exception("Invalid response %s." % resp['status'])
        access_token = dict(cgi.parse_qsl(content))
    
        flask.session['FITBIT_TOKEN'] = access_token['oauth_token']
        flask.session['FITBIT_TOKEN_SECRET'] = access_token['oauth_token_secret']
        return flask.redirect('/')
    
    @app.route('/sleep/')
    def sleep():
        context = {
        }
        env = Environment(loader=FileSystemLoader('templates'))
        return env.get_template('index.html').render(context)

    print 'Listening :8001...'
    d = wsgiserver.WSGIPathInfoDispatcher({'/': app})
    port = int(os.environ.get("PORT", 5000))    
    app.run(host='0.0.0.0', port=8000, use_debugger=True)
    server = wsgiserver.CherryPyWSGIServer(('0.0.0.0', 8001), d)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Do stuff")
    parser.add_argument('command', action="store", choices=['authenticate', 'load', 'server'])
    args = parser.parse_args()

    if args.command == 'authenticate':
        authenticate()
    if args.command == 'load':
        load()
    if args.command == 'server':
        server()