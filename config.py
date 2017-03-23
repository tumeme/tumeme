""" just our config-constants """
import os
import sys

# fix if __file__ is not defined (when called be exec in a shell script for example)
pathfix = os.path.abspath(os.path.dirname(sys.argv[0]))

DB_PATH = os.path.join(pathfix, "db/meme.db") # our database
IMG_DIR= os.path.join(pathfix, "img/") # where is the folder for the images of our frontpage?
QUEUE_DIR= os.path.join(pathfix, "queue/")
KACKCHA_DIR = os.path.join(pathfix, "kackchas/")

MAX_QUEUE_LEN=512 # how long is our meme-queue?
MAX_FRONTPAGE_LEN=80 # how many memes we deliver before deleting old ones?
IMG_PER_PAGE = 10

MAX_COOKIEJAR_ENTRIES=1024 # how many cookiejar-entries?
NUMBER_OF_KACKCHAS = 1024

# the tables of our db specified by DB_PATH
IMG_TABLE_NAME="img"
QUEUE_TABLE_NAME="queue"
COOKIEJAR_TABLE_NAME="cookiejar"

