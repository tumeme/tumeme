#!/usr/bin/env python3

# stdlib
import os
import random
import datetime
import math
from collections import OrderedDict

# werkzeug and jinja
from werkzeug.wrappers import Request, Response, BaseRequest
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.wsgi import SharedDataMiddleware
from werkzeug.utils import redirect
from werkzeug.utils import secure_filename
from jinja2 import Environment, FileSystemLoader

# custom  
from db_wrapper import Database
import config
import kackcha # haha, nice one boss
     
# our application class
class Tumeme(object):
    def __init__(self):
        if not (os.path.isfile(config.DB_PATH) and os.path.isdir(config.IMG_DIR) and os.path.isdir(config.QUEUE_DIR) ):
            print("the given img, db, or queue path points to nirvana")
            raise ValueError

        template_path = os.path.join(os.path.dirname(__file__), 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path),
                                 autoescape=True)

        self.url_map = Map([
                Rule("/", endpoint="main_page"),
                Rule("/upload", endpoint="upload_page"),
                Rule("/vote", endpoint="vote")
            ]) 
            
    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)

        try:
            endpoint, values = adapter.match()
            return getattr(self, endpoint)(request, **values)
        except NotFound as e:
            return self.error_404(request)
        # catch all other HTTPExceptions with generic error page
        except HTTPException as e:
            print("catched error, dude")
            return self.sum_ting_wong(request, str(e))
        
    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def render_template(self, template_name, **context):
        #TODO: caching 
        t = self.jinja_env.get_template(template_name)
        return Response(t.render(context), mimetype='text/html')


    """ the logic for the individual pages below  """
	
    def upload_page(self, request):
        """ upload page logic - does what you‘d expect """
        
        def allowed_file(filename):
            ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])
            """ see flask docs """
            return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
        

        # detect "kackcha-spam"
        identity = str(request.remote_addr) + str(request.user_agent) # not really secure, but might be good enough in many cases
        if len(Database.read(config.DB_PATH, "SELECT * FROM kackchas WHERE identity=?", payload=(identity, ), fetch_number=10)) > 8:
            print("User spammy with the kackchas")
            kackcha.delete_by_id(identity)

        # first captcha stuff
        captcha_url = os.path.join("kackchas", kackcha.create_new(identity) ) 
        if not captcha_url:
            return self.render_template("upload.html", error="Rolling out your own captcha: what could possibly go wrong? (sorry)")
        
        # now the actual upload magic
        if request.method == "POST":
            # first: is the captcha solved at all, and if so, correctly?
            valid_captcha_names = [ os.path.join("kackchas", kack[0]) for kack in Database.read(config.DB_PATH, "SELECT name FROM kackchas", fetch_number=config.NUMBER_OF_KACKCHAS) ]
            print((request.form["kackcha-name"], ) in valid_captcha_names)

            # user tried to be smart, tell him/her/it to fuck off
            if "kackcha" not in request.form or  "kackcha-name" not in request.form or request.form["kackcha-name"] not in valid_captcha_names:
                return self.render_template("upload.html", error="You messed around with the captchas, didn‘t you?", captcha_url=captcha_url) 

            expected_result = Database.read(config.DB_PATH, "SELECT solution FROM kackchas WHERE name=?", payload=(request.form["kackcha-name"].replace("kackchas/", "", 1), )) # TODO: less hacky 

            if not expected_result: 
                return self.render_template("upload.html", error="I fucked something up with the captchas, sorry.", captcha_url=captcha_url)

            # check if user entered the right solution for the captcha
            if str(expected_result[0][0]) != str(request.form["kackcha"]):
                kackcha._delete(request.form["kackcha-name"].replace("kackchas/", "", 1) ) #TODO: less hacky
                return self.render_template("upload.html", error="Captcha solution incorrect, so you‘re either brainlet or robot, can‘t tell.", captcha_url=captcha_url)
            else:
                # user solved captcha, delet dis
                try: 
                    kackcha._delete(request.form["kackcha-name"].replace("kackchas/", "", 1) ) #TODO: less hacky
                except:
                    print("kakcha already ded")

            # now bunch of checks if form data seems valid
            if not "picture" in request.files or not allowed_file(request.files["picture"].filename): # hey it‘s me ur de morgan
                return self.render_template("upload.html", error="This does not look like a picture, m‘harald.", captcha_url=captcha_url)
            elif not "title" in request.form or not "memetype" in request.form: 
                print(request.form)
                return self.render_template("upload.html", error="Your post needs a title and at least one keyword, m‘harald.", captcha_url=captcha_url)
            elif len(request.form["title"]) == 0 or len(request.form["title"]) > 42: # check for too long words
                return self.render_template("upload.html", error="Your title needs between one and 42 characters, m‘harald.", captcha_url=captcha_url)
            elif len(request.form["memetype"]) > 16 :
                return self.render_template("upload.html", error="No more than 16 characters for the memetype, m‘harald.", captcha_url=captcha_url)

            # okay, data seems kind of sane now, put the pic in our queue folder and save the metadata
            pic = request.files["picture"]
            filename = os.path.join(config.QUEUE_DIR, secure_filename(pic.filename) )

            # make sure we don‘t overwrite existing files
            while os.path.isfile(os.path.abspath(filename)) or os.path.isfile(os.path.abspath(os.path.join(config.IMG_DIR, os.path.split(filename)[1])) ):
                print(filename)
                filename = "".join(filename.split(".")[:-1]) + str(random.randrange(0,1000)) + "." + filename.split(".")[-1]

            pic.save(filename)
            
            # we insert the metadata of our image in the queue db, the MemeGatekeeper will keep track of which one‘s to actually deliver by putting them in /img and the corresponding img db
            metadata = (request.form["title"], request.form["memetype"],  os.path.split(filename)[1], datetime.datetime.now().isoformat(), "0", "0", "0") #    title, memetype, pic_url, date, upvotes
            Database.apply_query(config.DB_PATH, "INSERT INTO queue VALUES(?, ?, ?, ?, ?, ?, ?)", payload=metadata)
            
            # the user uploaded his image, back to the frontpage (we want the ones with the highest rank to be showed first)
            dankest_memes = Database.read(config.DB_PATH, "SELECT * FROM " + config.IMG_TABLE_NAME + " ORDER BY rank DESC", fetch_number=config.IMG_PER_PAGE)
            return redirect("/?success")

         
        return self.render_template("upload.html", captcha_url=captcha_url) 

    def main_page(self, request):
        """ the front page """
        
        info, error, already_voted  = None, None, None # should use attributes instead, but fuck oop
        if "success" in request.args:
            info = "Thanks for uploading dank memes, m‘harald."
        
        current_page = 0
        if "page" in request.args:
            try: 
                current_page = abs(int(request.args["page"]))
                if current_page > config.MAX_FRONTPAGE_LEN:
                    current_page = 0
                    info = "You outreached the last page. Congrats for not being normie."

            except: 
                print("unable to parse given page")
            
        dankest_memes = Database.read(config.DB_PATH,
                "SELECT * FROM " + config.IMG_TABLE_NAME + " ORDER BY rank DESC LIMIT " + str(config.IMG_PER_PAGE) + " OFFSET " + str(current_page*config.IMG_PER_PAGE),
                fetch_number=config.IMG_PER_PAGE)

        max_page = math.ceil(len(Database.read(config.DB_PATH, "SELECT * FROM " + config.IMG_TABLE_NAME, fetch_number=config.MAX_FRONTPAGE_LEN)) / config.IMG_PER_PAGE ) - 1

        # check if user already has user-id, if not. create a new one (this is just a temporary soulution)
        if not request.cookies.get("user-id"):
            identity = str(request.remote_addr) + str(request.user_agent) # not really secure, but might be good enough in many cases
            evil_user = len(Database.read(config.DB_PATH, "SELECT identity FROM cookiejar WHERE identity=?", payload=(identity, )) ) != 0
            if evil_user:
                error = "Don‘t delete cookies if you want to vote. Try again later."
                response = self.render_template("content.html", error=error, content=dankest_memes, current_page=current_page, max_page=max_page)
                return response
            else:
                response = self.render_template("content.html", error=error, content=dankest_memes, current_page=current_page, max_page=max_page)
                response.set_cookie("user-id", os.urandom(32) + "(nsa-random)".encode("utf-8"), max_age=60*60*8) #  8h  cookie TODO: use secure cookie
                return response
        else:
            # used to change the style of the buttons which the user already voted on
            already_voted = Database.read(config.DB_PATH, "SELECT pic_url, upvoted, downvoted FROM cookiejar WHERE uid=?", 
                    payload=(request.cookies.get("user-id"),),
                    fetch_number=config.MAX_FRONTPAGE_LEN)
            print(already_voted)
            # add vote_info of already_voted to the memes in dankest_memes TODO: make less ugly
            for i, meme in enumerate(dankest_memes):
                # select the matching vote info
                meme = list(meme)
                meme.append(None)
                dankest_memes[i] = meme # we want an additional element to store the vote-info
                for vote_info in already_voted:
                    if vote_info[0] == meme[2]: # pic_url == pic_url (TODO: result abstraction!)
                        print("vote-info", end="")
                        print(vote_info)
                        dankest_memes[i][-1] = vote_info[1:] #add the vote-info
                        break

 
        uid = request.cookies.get("user-id")
        identity = str(request.remote_addr) + str(request.user_agent) # not really secure, but might be good enough in many cases
        # identify user with same identity but other user-id-cookie -> fishy, probably just deleted his cookie -> cant post till identities get deleted (every 25 mins, see MemeGatekeeper)
        evil_user = len(Database.read(config.DB_PATH, "SELECT identity FROM cookiejar WHERE identity=? AND uid != ?", payload=(identity, uid )) ) != 0
        if evil_user:
            error = "Don‘t delete cookies if you want to vote. Try again later."
        return self.render_template("content.html", content=dankest_memes, info=info, error=error, current_page=current_page, max_page=max_page)


    def vote(self, request):
        """ implementation of up/downvotes: the client sends an asynchronous POST-request """

        if request.method == "POST" and "vote" in request.form and "post" in request.form and request.cookies.get("user-id"): 
            #print("vote: " + request.form["vote"] + "\n post: " + request.form["post"]) 
            
            uid = request.cookies.get("user-id")
            pic_url = request.form["post"]
            vote = request.form["vote"]

            identity = str(request.remote_addr) + str(request.user_agent) # not really secure, but might be good enough in many cases
            evil_user = len(Database.read(config.DB_PATH, "SELECT identity FROM cookiejar WHERE identity=? AND uid != ?", payload=(identity, uid )) ) != 0
            if evil_user:
                print("evil user detected")
                return redirect("/") # just do nothing

            # does the given meme even exist?
            if Database.read(config.DB_PATH, "SELECT * FROM img WHERE pic_url=?", payload=(pic_url, ) ):
                user_history = Database.read(config.DB_PATH, "SELECT * FROM cookiejar WHERE uid=? AND pic_url=?", payload=(uid, pic_url), 
                                                result_abstraction=OrderedDict([("uid", ""), ("post", ""), ("upvoted", ""), ("downvoted", ""), ("identity", "")]))
                
                # user has not voted on the meme given by pic_url
                if not user_history:
                    # check if still space
                    stored_cookies = Database.read(config.DB_PATH, "SELECT uid FROM cookiejar", fetch_number=config.MAX_COOKIEJAR_ENTRIES) 
                    # if not, delete the 40 first cookies
                    if len(stored_cookies) == config.MAX_COOKIEJAR_ENTRIES:
                        for i in range(40):
                            Database.apply_query(config.DB_PATH, "DELETE FROM cookiejar WHERE uid=?", payload=(stored_cookies[i][0],))

                    payload = (uid, pic_url, int(vote == "up"), int(vote == "down"), identity)
                    Database.apply_query(config.DB_PATH, "INSERT INTO cookiejar VALUES(?, ?, ?, ?, ?)", payload)
                    if vote == "up":
                        Database.apply_query(config.DB_PATH, "UPDATE img SET upvotes=upvotes+1 WHERE pic_url=?", payload=(pic_url, ))
                    elif vote =="down":
                        Database.apply_query(config.DB_PATH, "UPDATE img SET downvotes=downvotes+1 WHERE pic_url=?", payload=(pic_url, ))

                # user wants to upvote, but has already downvoted the same meme 
                elif request.form["vote"] == "up" and user_history[0]["upvoted"] == 0:
                    Database.apply_query(config.DB_PATH, "UPDATE img SET downvotes=downvotes-1, upvotes=upvotes+1 WHERE pic_url=?", payload=(pic_url,))
                    Database.apply_query(config.DB_PATH, "UPDATE cookiejar SET upvoted=1, downvoted=0 WHERE pic_url=? AND uid=?", payload=(pic_url, uid) )

                # user wants to downvote, but has already upvoted the same meme 
                elif request.form["vote"] == "down" and user_history[0]["downvoted"] == 0:
                    Database.apply_query(config.DB_PATH, "UPDATE img SET upvotes=upvotes-1, downvotes=downvotes+1 WHERE pic_url=?", payload=(pic_url,) )
                    Database.apply_query(config.DB_PATH, "UPDATE cookiejar SET upvoted=0, downvoted=1 WHERE pic_url=? AND uid=?", payload=(pic_url, uid) )

        votes = Database.read(config.DB_PATH, "SELECT upvotes, downvotes FROM img WHERE pic_url=?", payload=(request.form["post"],))
        if not votes or len(votes[0]) != 2:
            votes = (0, 0)
        return Response(str(votes[0][0]) +  " " + str(votes[0][1]), mimetype="text/plain")

    def error_404(self, request):
        return self.render_template("404.html")

    def sum_ting_wong(self, request, e):
        return self.render_template("sumtingwong.html", error=e)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


""" used to fix bug where connection resets when a RequestEntityTooLarge occurs (only relevant for dev-server) (see: http://flask.pocoo.org/snippets/47/)"""
from werkzeug.wsgi import LimitedStream
class StreamConsumingMiddleware(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        stream = LimitedStream(environ['wsgi.input'],
                               int(environ['CONTENT_LENGTH'] or 0))
        environ['wsgi.input'] = stream
        app_iter = self.app(environ, start_response)
        try:
            stream.exhaust()
            for event in app_iter:
                print("asdf")
                yield event
        finally:
            if hasattr(app_iter, 'close'):
                app_iter.close()

""" endfix"""

# app factory creates new instances of our app
def create_app(setup=False):
    if setup:
        Database.apply_query(config.DB_PATH, "CREATE table queue (title text, memetype text, pic_url text, date text, upvotes integer, downvotes integer, rank integer)") # for our img-queue, used to store file-uploads temporarily before visible     
        Database.apply_query(config.DB_PATH, "CREATE table img (title text, memetype text, pic_url text, date text, upvotes integer, downvotes integer, rank integer)") # for theimages that made it past the queue
        Database.apply_query(config.DB_PATH, "CREATE table cookiejar (uid text, pic_url text, upvoted integer, downvoted integer, identity text)")
        Database.apply_query(config.DB_PATH, "CREATE table cookiejar (uid text, pic_url text, upvoted integer, downvoted integer, identity text)")
    
    # limit the file-upload size to 10mb
    BaseRequest.max_content_length = 10* 1024*1024
    BaseRequest.max_from_memory_size = 10* 1024*1024
    class Request(BaseRequest):
        pass

    app = Tumeme()
    app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {
        "/static": os.path.join(os.path.dirname(__file__), "static"),
        "/img": os.path.join(os.path.dirname(__file__), "img"), 
        "/kackchas": os.path.join(os.path.dirname(__file__), "kackchas")
        })
    
    # apply the requestEntityTooLarge connection reset fix
    #app.wsgi_app = StreamConsumingMiddleware(app.wsgi_app)
    return app
    


if __name__ == "__main__":
    from werkzeug.serving import run_simple
    app = create_app(setup=True)
    run_simple("0.0.0.0", 5000, app, use_debugger=True, use_reloader=True)

