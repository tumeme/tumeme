import os
import sys
import time
from PIL import Image

import config
from db_wrapper import Database

def resize_all(directory=config.IMG_DIR):
    for root, dirs, files in os.walk(directory):
        for img in files:
            if img.split(".")[-1] not in ["jpg", "jpeg", "png", "gif"]:
                continue
            with Image.open(os.path.join(root, img)) as im:
                if im.size[0] <= 1024:
                    break
                im = im.resize( (1024, int(im.size[1] * 1024/im.size[0])) ) # sclae image (we want a width of 1024)
                filename = os.path.abspath(os.path.join(root, img)) 
                print(filename + " resized")
                im.save(filename)

def delete_invalid_pics(directory=config.IMG_DIR):
    pic_names = Database.read(config.DB_PATH, "SELECT pic_url FROM img", fetch_number=config.MAX_FRONTPAGE_LEN)
    pic_names = [name[0] for name in pic_names]
    invalid_pic_names = list()
    for name in pic_names:
        try: 
            with Image.open(os.path.join(config.IMG_DIR, name)) as img:
                continue
        except:
            print("invalid pic detected")
            invalid_pic_names.append(name)

    if len(invalid_pic_names) > 0:
        Database.apply_query(config.DB_PATH, "DELETE FROM img WHERE pic_url IN (" + ("?,"*len(invalid_pic_names))[:-1] + ")", payload=tuple(invalid_pic_names) )
        for name in invalid_pic_names:
            os.remove(os.path.join(config.IMG_DIR, name)) # TODO: this might be exploited if the secure_filename function of tumeme.py fails, but what the hell
    

        
if __name__ == "__main__":
    while 1:
        resize_all()
        time.sleep(5)

