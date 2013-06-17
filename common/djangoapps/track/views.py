import json
import logging
import pytz
import datetime
import dateutil.parser

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect
from django.conf import settings
from mitxmako.shortcuts import render_to_response

from django_future.csrf import ensure_csrf_cookie
from track.models import TrackingLog
from pytz import UTC

log = logging.getLogger("tracking")

LOGFIELDS = ['username', 'ip', 'event_source', 'event_type', 'event', 'agent', 'page', 'time', 'host']


def log_event(event):
    event_str = json.dumps(event)
    log.info(event_str[:settings.TRACK_MAX_EVENT])
    if settings.MITX_FEATURES.get('ENABLE_SQL_TRACKING_LOGS'):
        event['time'] = dateutil.parser.parse(event['time'])
        tldat = TrackingLog(**dict((x, event[x]) for x in LOGFIELDS))
        try:
            tldat.save()
        except Exception as err:
            log.exception(err)


def user_track(request):
    try:  # TODO: Do the same for many of the optional META parameters
        username = request.user.username
    except:
        username = "anonymous"

    try:
        scookie = request.META['HTTP_COOKIE']  # Get cookies
        scookie = ";".join([c.split('=')[1] for c in scookie.split(";") if "sessionid" in c]).strip()  # Extract session ID
    except:
        scookie = ""

    try:
        agent = request.META['HTTP_USER_AGENT']
    except:
        agent = ''

    # TODO: Move a bunch of this into log_event
    event = {
        "username": username,
        "session": scookie,
        "ip": request.META['REMOTE_ADDR'],
        "event_source": "browser",
        "event_type": request.GET['event_type'],
        "event": request.GET['event'],
        "agent": agent,
        "page": request.GET['page'],
        "time": datetime.datetime.now(UTC).isoformat(),
        "host": request.META['SERVER_NAME'],
        }
    log_event(event)
    return HttpResponse('success')


def server_track(request, event_type, event, page=None):
    try:
        username = request.user.username
    except:
        username = "anonymous"

    try:
        agent = request.META['HTTP_USER_AGENT']
    except:
        agent = ''

    event = {
        "username": username,
        "ip": request.META['REMOTE_ADDR'],
        "event_source": "server",
        "event_type": event_type,
        "event": event,
        "agent": agent,
        "page": page,
        "time": datetime.datetime.now(UTC).isoformat(),
        "host": request.META['SERVER_NAME'],
        }

    if event_type.startswith("/event_logs") and request.user.is_staff:  # don't log
        return
    log_event(event)


@login_required
@ensure_csrf_cookie
def view_tracking_log(request, args=''):
    if not request.user.is_staff:
        return redirect('/')
    nlen = 100
    username = ''
    if args:
        for arg in args.split('/'):
            if arg.isdigit():
                nlen = int(arg)
            if arg.startswith('username='):
                username = arg[9:]

    record_instances = TrackingLog.objects.all().order_by('-time')
    if username:
        record_instances = record_instances.filter(username=username)
    record_instances = record_instances[0:nlen]

    # fix dtstamp
    fmt = '%a %d-%b-%y %H:%M:%S'  # "%Y-%m-%d %H:%M:%S %Z%z"
    for rinst in record_instances:
        rinst.dtstr = rinst.time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('US/Eastern')).strftime(fmt)

    return render_to_response('tracking_log.html', {'records': record_instances})
