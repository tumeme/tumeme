#!/usr/bin/env python3

import datetime
import time
import math
import os
from collections import OrderedDict

from db_wrapper import Database
import config
import kackcha
import ImageResizer

class MemeGatekeeper(object):
    """ runs in the background to assess the memes in the queue to put them in the img-folder when memes in there get stale 
        kinda became an eierlegendewollmilchsau, but fuck it
    """

    
    def __init__(self):
        pass

    def _get_n_memes(self, table:str, num_of_memes=None) -> list:
        if not num_of_memes:
            if table == "queue": num_of_memes = config.MAX_QUEUE_LEN
            else: num_of_memes = config.MAX_FRONTPAGE_LEN

        # CREATE table queue (title text, memetype text, pic_url text, date text, upvotes integer, downvotes integer, rank integer) (structure of our db)
        result_abstraction = OrderedDict([
            ("text", ""),  ("memetype", ""), ("pic_url", ""), ("date", ""),
            ("upvotes", ""), ("downvotes", ""), ("rank", "")
            ])
        # gotta catch em all
        return Database.read(config.DB_PATH, "SELECT * FROM " + table, fetch_number=num_of_memes, result_abstraction=result_abstraction)

    def calculate_memerank(self):
        def _calculate_rank(meme_dict:OrderedDict) -> float:
            """ high rank <=> dank meme; low rank <=> stale meme"""
            meme_time = datetime.datetime.strptime(meme["date"], "%Y-%m-%dT%H:%M:%S.%f")
            now_time = datetime.datetime.now()
            age_in_secs = abs((now_time - meme_time).total_seconds()) + 1
            upvotes, downvotes = int(meme_dict["upvotes"]), int(meme_dict["downvotes"])
            
            # TODO: for very high upvote-counts modify the equation with log() or something
            return round (5 + upvotes - downvotes  - age_in_secs/(1200*6), 3) # one new upvote reverts the loss of meme-value that occurs in 120 minutes

        # TODO: this has horrible implications in terms of performance, but what the fuck
        img_memes = self._get_n_memes("img") 
        for meme in img_memes:
            rank = _calculate_rank(meme)
            # every meme has an unigque pic_url. what could possibly go wrong?
            Database.apply_query(config.DB_PATH, "UPDATE img SET rank = ? WHERE pic_url=?", payload=(rank, meme["pic_url"]) )
    
    # don‘t EVER use user data for the table param, just don‘t (I know, lazy)
    def _delete_memes(self, table:str, to_delete:list):
        """ deletes memes from db """
        payload = tuple([meme["pic_url"] for meme in to_delete] )
        # kind of hacky/borderline stupid
        payload_string = ("?," * len(to_delete))[:-1]
        Database.apply_query(config.DB_PATH, "DELETE FROM " + table +  " WHERE pic_url IN (" + payload_string + ")", payload)
	
        # determine the directory-path we have to delete from
        delete_dir = ""
        if table == "queue":
            delete_dir = config.QUEUE_DIR
        else:
            delete_dir = config.IMG_DIR
	
        for meme in to_delete:
            if os.path.isfile(os.path.abspath(os.path.join(delete_dir, meme["pic_url"]))):
                os.remove(os.path.join(delete_dir, meme["pic_url"]) )
          
    
    def _promote_memes(self, to_promote):
        """ used by the update frontpage method """
        # TODO: make less stupid
        for meme in to_promote:
            payload = tuple([ meme[key] for key in meme])
            assert len(payload) == 7, "invalid payload length, should be 7 but is " + str(len(payload))
            Database.apply_query(config.DB_PATH, "INSERT INTO img VALUES (?, ?, ?, ?, ?, ?, ?)", payload=payload)

            # move the file
            os.rename(os.path.join(config.QUEUE_DIR, meme["pic_url"]), 
                     os.path.join(config.IMG_DIR, meme["pic_url"]) 
                    )
        
        # now delete the old data base entries
        self._delete_memes("queue", to_promote)
        
         

    def update_frontpage(self):
        """ puts the dankest memes in our frontpage folder (~/img) and deletes stale memes """
        frontpage_memes = self._get_n_memes("img")
        queue_memes = self._get_n_memes("queue")
        
        # delete shitposts if 20 downvotes or difference between up and down greater <= -10
        for meme in frontpage_memes:
            if int(meme["upvotes"] - meme["downvotes"]) <= -10 or int(meme["downvotes"]) > 5:
                self._delete_memes("img", [meme])

        # if queue not empty
        if len(queue_memes) > 0:
            # if your frontpage is not full, we don‘t have to consider the meme-reankings and just put the newest memes there
            if len(frontpage_memes) < config.MAX_FRONTPAGE_LEN:
                unused_slots = config.MAX_FRONTPAGE_LEN - len(frontpage_memes)
                self._promote_memes(self._get_n_memes("queue", num_of_memes=unused_slots) )
            
            else:
                # we have to delete a meme from the meme-folder to get one from the queue to the frontpage, we‘ll delete the one with the worst ranking
                frontpage_memes.sort(key=lambda meme: int(meme["rank"]))
                self._delete_memes("img", frontpage_memes[:math.ceil(config.MAX_FRONTPAGE_LEN / 2)] ) # delete 50% of the memes (the ones with the lowest rank)

    def _flush_identities(self):
        """ removes the cols used for the identification of users who delete cookies (if we didn‘t not do this, we might lock out users from upvoting) """
        Database.apply_query(config.DB_PATH, "UPDATE cookiejar SET identity=''")
    
    def start(self):
        queue_memes = self._get_n_memes("queue") 
        img_memes = self._get_n_memes("img")
        #self._delete_memes("queue", queue_memes) # DEBUG!!!!!!!!!!!!!!!!!!!!!!11
        #self._delete_memes("img", img_memes)     # !!!!!!!!!!!!!!!!!!!!!!!!!!!11
        #Database.apply_query(config.DB_PATH, "DELETE FROM " + config.COOKIEJAR_TABLE_NAME)
        #kackcha.create_new(setup=True) # kill me plz
        
	# ugly, but works (just like a good ol soviet russian factory worker heh)
        i = 0
        while 1:
            ImageResizer.delete_invalid_pics()
            kackcha.clean()
            # every ~24 mins
            if i > 60*24: 
                i = 0
                self._flush_identities()
                ImageResizer.resize_all() # make them fit in (the ImageResizer acts just like a fucking normie)
    
            self.calculate_memerank()
            self.update_frontpage()
            time.sleep(1)
            i += 1

if __name__ == "__main__":
    gatekeeper = MemeGatekeeper()
    gatekeeper.start()

    
