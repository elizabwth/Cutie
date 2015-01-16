#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import gdata
import gdata.youtube 
import gdata.youtube.service
from utils import *

import socket
import sys
import time
import threading

import Pyro4.core
import Pyro4.naming
import Pyro4.socketutil

import logging

logging.basicConfig(stream=sys.stderr, format="[%(asctime)s,%(name)s,%(levelname)s] %(message)s")
log = logging.getLogger("Pyro4")
log.setLevel(logging.WARNING)

class Server:
    def __init__(self):
        self.users = []
        self.queue = []
        self.sync_data = {}

    def run(self):
        def tick():
            while True:
                time.sleep(0.5)
                self.sync_users_with_curator()

        thread = threading.Thread(target=tick)
        thread.setDaemon(True)
        thread.start()

    def get_queue(self):
        return self.queue

    def get_users(self):
        return self.users

    def get_sync_data(self):
        return self.sync_data

    def sync_users_with_curator(self):
        # get sync data from curator
        for user in self.users:
            if user['group'] == 'curator':
                user['callback_handler'].sync_data_requested()
                break

        # set sync data received from curator for all non-curators
        for user in self.users:
            if user['group'] != 'curator' and self.sync_data != {}:
                user['callback_handler'].sync_player(self.sync_data)

    @Pyro4.oneway
    def broadcast_message(self, name, message):
        for user in self.users:
            user['callback_handler'].message_received(name, message)

        print("<"+name+"> "+message)

    @Pyro4.oneway
    def connect_user(self, name, group, callback_handler):
        u = {}
        u['name']  = name
        u['group'] = group
        u['callback_handler'] = callback_handler
        self.users.append(u)

        for user in self.users:
            user['callback_handler'].user_connected(u)

        print("User connected: "+u['name']+", "+u['group'])

    @Pyro4.oneway
    def disconnect_user(self, name):
        index = 0
        user_found = False
        for i, user in enumerate(self.users):
            if user['name'] == name:
                self.users.remove(user)
                index = i
                user_found = True
                break
        
        if user_found:
            for user in self.users:
                user['callback_handler'].user_disconnected(index)

            print("User disconnect at index: "+str(index))

    @Pyro4.oneway
    def add_video(self, url, user_name):
        # add something that will check if a video can be embedded or not
        # if it can't, send the user that added it a callback stating that 
        # the video could not be added to the queue
        vid_id     = get_video_id(url)
        yt_service = gdata.youtube.service.YouTubeService()
        entry      = yt_service.GetYouTubeVideoEntry(video_id=vid_id)

        qi             = {}
        qi['vid_id']   = vid_id
        qi['title']    = entry.media.title.text
        qi['views']    = entry.statistics.view_count
        qi['rating']   = entry.rating.average
        qi['duration'] = entry.media.duration.seconds
        qi['added_by'] = user_name
        self.queue.append(qi)

        for user in self.users:
            user['callback_handler'].video_added(qi)

        print("Video added: "+qi['vid_id'])

    @Pyro4.oneway
    def remove_video(self, index):
        self.queue.pop(index)

        for user in self.users:
            user['callback_handler'].video_removed(index)

        print("Video removed at index: "+str(index))

    @Pyro4.oneway
    def sort_queue(self, initial, dropped):
        self.queue[initial], self.queue[dropped] = self.queue[dropped], self.queue[initial]

        for user in self.users:
            if user['group'] != 'curator':
                user['callback_handler'].queue_sorted(initial, dropped)

        print("Queue item sorted from row {0} to {1}".format(initial, dropped))

    @Pyro4.oneway
    def set_sync_data(self, vid_id, time, state, queue_index):
        self.sync_data['vid_id']      = vid_id
        self.sync_data['time']        = time
        self.sync_data['state']       = state
        self.sync_data['queue_index'] = queue_index

def main():
    server = Server()

    daemon = Pyro4.Daemon(host = socket.gethostbyname(socket.gethostname()), port = 8080)
    server_uri = daemon.register(server, "cutie")

    server.run()
    print("Server running, uri = "+str(server_uri))
    daemon.requestLoop()

if __name__ == '__main__':
    main()