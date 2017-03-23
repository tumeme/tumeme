#!/usr/bin/env python3

import os
import time
import datetime
from random import randrange

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from db_wrapper import Database
import config

def create_new(identity=None, setup=False)->str:
    def generate_image():
        """ generates an image object of a random kackcha """
        img = Image.new("RGB", (128, 40), (255,255,255))
        img.background = (255,244,245)
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype("comic-sans.ttf", 24) # do it for the memes

        draw.rectangle([0,0, img.size[0], img.size[1]], fill=(255,255,254) )
       
        params = [randrange(-200, 200), randrange(0, 200)]   
        correct_result = params[0] + params[1] 
        txt = "{}+{}".format(*params)
        draw.text((10, 0) , txt, font=font, fill=(randrange(5,6),randrange(10, 100),randrange(0, 255)) )
        return img, correct_result

    if setup:
        Database.apply_query(config.DB_PATH, "CREATE TABLE kackchas (name text, solution integer, date text, identity text)")
        Database.apply_query(config.DB_PATH, "DELETE FROM kackchas")
    
        # delete the old kaptchas (what could possibly go wrong is left as an exercice to the reader)
        Database.apply_query(config.DB_PATH, "DELETE FROM kackchas")
        to_delete = os.listdir(config.KACKCHA_DIR)
        for kackcha in to_delete: 
            if kackcha[-3:] == "png": 
                os.remove(os.path.join(config.KACKCHA_DIR, kackcha) )
        
    if not identity:
        return

    # check if enough space for new kackchas
    kackchas = Database.read(config.DB_PATH, "SELECT name FROM kackchas ORDER BY rowid ASC",fetch_number=config.NUMBER_OF_KACKCHAS)
    while len(kackchas) >= config.NUMBER_OF_KACKCHAS:
        # the memeGatekeeper should clean the old kackchas.
        kackchas = Database.read(config.DB_PATH, "SELECT name FROM kackchas ORDER BY rowid ASC",fetch_number=config.NUMBER_OF_KACKCHAS)
        print("too many kackchas, wait")

   # create a new  kackcha 
    img, correct_result = generate_image() 
    # the name we want to save our captcha to
    name = str(randrange(0, 100)) + datetime.datetime.now().isoformat() + ".png"
    # repeat till unique
    while os.path.isfile(os.path.join(config.KACKCHA_DIR, name)):
        name = str(randrange(0, 10000)) + datetime.datetime.now().isoformat() + ".png"
    
    # drop da gauss
    img = img.filter(ImageFilter.GaussianBlur(radius=1))    
    img.save(os.path.join(config.KACKCHA_DIR, name), "PNG" )

    # save the expected result in database along with the name of the captcha and the creation date (we want to delete captchas older than two minutes
    Database.apply_query(config.DB_PATH, "INSERT INTO kackchas VALUES (?, ?, ?, ?)", payload=(name, correct_result, datetime.datetime.now().isoformat(), identity))
    
    return name


def _delete(name):
    os.remove(os.path.join(config.KACKCHA_DIR, name) )
    Database.apply_query(config.DB_PATH, "DELETE FROM kackchas WHERE name=?", payload=(name,))
    print("deleted")


def delete_by_id(identity):
    to_delete = Database.read(config.DB_PATH, "SELECT name FROM kackchas WHERE identity=?", payload=(identity, ))
    for kack in to_delete:
        _delete(kack[0])
    

def clean():
    kackchas = Database.read(config.DB_PATH, "SELECT name, date FROM kackchas", fetch_number=config.NUMBER_OF_KACKCHAS)
    for kackcha in kackchas:
        # delete kackcha if older than two minutes
        if ( datetime.datetime.now() - datetime.datetime.strptime(kackcha[1], "%Y-%m-%dT%H:%M:%S.%f") ).total_seconds() >= 120:
            _delete(kackcha[0])

if __name__ == "__main__":
    # debug
    pass
