import urllib
import urllib2
import urlparse

from django.http import HttpResponse
from django.http import HttpResponseForbidden

try:
    import json as simplejson
    simplejson.loads
except (ImportError, AttributeError):
    try:
        import simplejson
        simplejson.loads
    except (ImportError, AttributeError):
        try:
            from django.utils import simplejson
            simplejson.loads
        except (ImportError, AttributeError):
            import jsonlib as simplejson
            simplejson.loads


class Request(urllib2.Request):
    def __init__(self, *args, **kwargs):
        self.method = kwargs.pop('method', None)
        content_type = kwargs.pop('content_type', None)
        urllib2.Request.__init__(self, *args, **kwargs)
        if content_type:
            self.add_unredirected_header('Content-type', content_type)

    def get_method(self):
        if self.method:
            return self.method.upper()
        return urllib2.Request.get_method(self)

def urlencode(query, doseq=0):
    def to_utf8(s):
        if isinstance(s, unicode):
            return s.encode('utf-8')
        return s
    query = dict(query)
    for k, v in query.items():
         if isinstance(v, (list,tuple)):
             query[k] = [to_utf8(i) for i in v]
         else:
             query[k] = to_utf8(v)
    return urllib.urlencode(query, doseq)


class Graph(object):
    FACEBOOK_GRAPH_SCHEME = 'https'
    FACEBOOK_GRAPH_BASE = 'graph.facebook.com'

    def __init__(self, facebook, path=None):
        self._facebook = facebook
        self._path = [path] if isinstance(path, basestring) else path or []

    def filter(self, path):
        return Graph(self._facebook, self._path + [path])

    def multiquery(self, ids, access_token=None):
        query = {'ids': u','.join(ids)}
        return self._request('GET', data=None, access_token=access_token, query=query)

    def _read(self, request):
        if self._facebook.proxy:
            proxy_handler = urllib2.ProxyHandler(self._facebook.proxy)
            opener = urllib2.build_opener(proxy_handler)
            response = opener.open(request).read()
        else:
            response = urllib2.urlopen(request).read()
        return response

    def get_url(self, query=None):
        query = query or {}
        query = urllib.urlencode(query)
        url = urlparse.urlunparse((
            self.FACEBOOK_GRAPH_SCHEME,
            self.FACEBOOK_GRAPH_BASE,
            '/' + '/'.join(self._path),
            '',
            query,
            '',
        ))
        return url

    def _request(self, method, data=None, access_token=None, content_type=None, query=None):
        query = query or {}
        access_token = access_token or getattr(self._facebook, 'oauth2_token', None)
        if access_token:
            query['access_token'] = access_token
        url = self.get_url(query)
        request = Request(url, data, method=method, content_type=content_type)
        response = self._read(request)
        if response:
            return simplejson.loads(response)
        return None

    def get(self, access_token=None):
        if not self._path:
            raise AttributeError('No path given to graph object')
        return self._request('GET', data=None, access_token=access_token)

    def post(self, data, access_token=None):
        if not self._path:
            raise AttributeError('No path given to graph object')
        data = urlencode(data, True)
        return self._request('POST', data, access_token=access_token)

    def delete(self, access_token=None):
        if not self._path:
            raise AttributeError('No path given to graph object')
        return self._request('DELETE', data=None, access_token=access_token)

    def __iter__(self):
        return iter(self.get())

    def __set__(self, val):
        return self.post(val)

    def get_app_access_token(self):
        query = urllib.urlencode({
            'client_id': self._facebook.app_id,
            'client_secret': self._facebook.app_secret,
            'type': 'client_cred',
        })
        url = urlparse.urlunparse((
            self.FACEBOOK_GRAPH_SCHEME,
            self.FACEBOOK_GRAPH_BASE,
            '/oauth/access_token',
            '',
            query,
            '',
        ))
        request = Request(url)
        response = self._read(request)
        values = urlparse.parse_qs(response)
        return values['access_token'][0]

    def get_user_access_token(self, session_key):
        query = urllib.urlencode({
            'client_id': self._facebook.app_id,
            'client_secret': self._facebook.app_secret,
            'type': 'client_cred',
            'sessions': session_key,
        })
        url = urlparse.urlunparse((
            self.FACEBOOK_GRAPH_SCHEME,
            self.FACEBOOK_GRAPH_BASE,
            '/oauth/exchange_sessions',
            '',
            query,
            '',
        ))
        request = Request(url)
        response = self._read(request)
        values = simplejson.loads(response)
        return values[0]['access_token']

def subscription_callback(token):
    '''
    Use this to wrap views that are supposed to be used as real-time
    subscription callbacks.

    @subscription_callback('someUniqueToken')
    def someview(request, data):
        pass
    '''
    def inner_decorator(view):
        def wrapped(request, *args, **kwargs):
            if request.method == 'GET':
                hub_mode = request.GET.get('hub.mode', None)
                hub_challenge = request.GET.get('hub.challenge', None)
                hub_verify_token = request.GET.get('hub.verify_token', None)
                if hub_mode != 'subscribe' \
                        or not hub_challenge \
                        or hub_verify_token != token:
                    return HttpResponseForbidden('')
                return HttpResponse(hub_challenge)
            else:
                data = simplejson.loads(request.raw_post_data)
                return view(request, data, *args, **kwargs)
        wrapped.token = token
        return wrapped
    return inner_decorator

if __name__ == '__main__':
    class Fakebook(object):
        oauth2_token = '' # put a valid token here
        proxy = None
    g = Graph(Fakebook())
    print g.filter('btaylor').get()

