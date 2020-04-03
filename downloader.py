#!/usr/bin/env python3

##### pre-requisites: #####
# $ pip install m3u8==0.5.4 pysrt==1.1.2 webvtt-py==0.4.4 --force-reinstall
# (there may be failures for optional sub-dependencies; they should be fine to ignore)
# ffmpeg needs to be in the PATH
###########################

unicode_fixes = {
    r'fianc�e': 'fiancée'
}



import re
from urllib.request import urlopen, Request
import json
import m3u8
import html
from webvtt import WebVTT
from pysrt.srtitem import SubRipItem
from pysrt.srttime import SubRipTime
from time import sleep
import subprocess

print('Welcome! Please ensure ffmpeg is in your PATH.')
print('Open your browser\'s network tab and select the video JSON descriptor URL.')
print('Right-click it, and select "Copy as cURL". Any variant of it will work, just not the "copy all" ones.')
curl = input('Paste the cURL command here: ')

print('Retrieving JSON...')
url = re.search(r'curl [\'"]([^\'"]+)[\'"]', curl).group(1)
accept_header = re.search(r' -H [\'"][Aa]ccept:\s([^\'"]+)[\'"]', curl).group(1)
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/74.0", "Accept": accept_header}
request = Request(url, headers=headers)
master_json = {}
with urlopen(request) as requrl:
    master_json = json.load(requrl)

print('Downloading subtitles...')
vtt_url = master_json['text_tracks'][0]['src']
with urlopen(vtt_url) as vtturl:
    data = vtturl.read()
    with open('subs.vtt', 'wb') as vtt:
        vtt.write(data)

print('Converting and validating subtitles...')
with open('subs.srt', 'w') as srt:
    index = 0
    for caption in WebVTT().read("subs.vtt"):
            index += 1
            for find, replace in unicode_fixes.items():
                caption.text = re.sub(find, replace, caption.text)
            if caption.text.find('�') > -1:
                raise Exception('FIXME: Found bad Unicode character at time index ' + caption.start + ': ' + caption.text)
            start = SubRipTime.from_ordinal(round(caption.start_in_seconds*1000))
            end = SubRipTime.from_ordinal(round(caption.end_in_seconds*1000))
            srt.write(SubRipItem(index, start, end, html.unescape(caption.text)).__str__() + "\n")

print('Downloading poster...')
poster_url = master_json['poster']
with urlopen(poster_url) as posterurl:
    data = posterurl.read()
    with open('cover.jpg', 'wb') as posterjpg:
        posterjpg.write(data)

print('Downloading master playlist...')
master_playlist = m3u8.load(master_json['sources'][1]['src'])

print('Finding best quality rendition...')
best_playlist = master_playlist.playlists[0]
for playlist in master_playlist.playlists:
    if playlist.stream_info.bandwidth > best_playlist.stream_info.bandwidth:
        best_playlist = playlist
playlist_audio_url = None
for medium in best_playlist.media:
    if medium.type == 'AUDIO':
        playlist_audio_url = medium.uri

print('Found video: ' + best_playlist.uri)
print('Found audio: ' + playlist_audio_url)

print('Calling ffmpeg to download and mux everything - this will take a while...', flush=True)
sleep(2)
subprocess.check_call(['ffmpeg', '-loglevel', 'info', '-y', '-reconnect', '1', '-reconnect_streamed', '1',
    '-i', best_playlist.uri, '-i', playlist_audio_url,'-i', 'subs.srt', '-c', 'copy',
    '-bsf:a', 'aac_adtstoasc', '-c:s', 'srt', '-metadata:s:s:0', 'language=eng',
    '-attach', 'cover.jpg', '-metadata:s:t', 'mimetype=image/jpeg', 'output.mkv'])

print('Done!')
