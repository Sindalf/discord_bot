import asyncio
import json
import urllib.error
import urllib.request
import re
from bs4 import BeautifulSoup
from discord.ext import commands
import discord
import random
import password
import requests
from Manga import manga
import mysql.connector

bot = commands.Bot(command_prefix='!', description='bot owned by Sindalf.')



class cookies_obj:
    def __init__(self):
        self.cookies = None
        
    def setCookie(self, cookie):
        self.cookies = cookie
        
cookies = cookies_obj()


async def get_html(url,cookies=None, headers=None):
    try:
        data = requests.get(url, timeout=10,cookies=cookies, headers=headers)
        data.encoding = 'utf-8'
        return data.text
    except:  # For some reason HTTPError wouldnt catch an HTTPError ?
        print('http error in get link')
        return None

async def detect_magazine_text(soup):
    if soup is not None:
        try:
            a = soup.find('div', class_="row-left", text='Magazine')  # Find Magazine box
            text = a.next_sibling.next_sibling.text  # if it exists then we get a value, otherwise None
            return text
        except:
            pass
    return None

async def detect_store_link(soup):
    if soup is not None:
        
        a = soup.findAll('a', {'class': re.compile('button icon green( js-purchase-product)?')})  # Find green button class

        for x in range(0, len(a)):  # loop through multiple green buttons
            try:
                link = a[x]['href']  # Find green button with a link
                if link.find('store.fakku.net') != -1:  # Make sure that link contains a store link
                    return link  # return store link
            except:
                pass  # 'href' access wont work if it doesn't exist
    return None  # return nothing if store link does not exist        

async def detect_read_link(soup):
    if soup is not None:
        c = soup.find('div', class_="images")
        b = c.a['href']
        return b
    
@bot.command(description="random manga from fakku")
async def rand():
    print(type(cookies.cookies))
    r = requests.get('https://www.fakku.net/hentai/random', cookies=cookies.cookies)
    print(r)
    soup = BeautifulSoup(r.text, 'html.parser')
    link = await detect_read_link(soup)
    name = link[8:-12]
    a = requests.get("https://api.fakku.net/manga/"+name, cookies=cookies.cookies, headers={'Sindalf': 'True'})
    print(a)
    book_json = a.json()['content']
    m = manga(book_json)
    m.populate()
    store_link = await detect_store_link(soup)  # see if the store link exists
    m.set_store_link(store_link)  # set store link
    magazine_text = await detect_magazine_text(soup)  # see if the magazine link exists
    m.set_magazine_text(magazine_text)  # set magazine link
    release_string = await manga_string(m, 'Random Manga! \n')
    await bot.say(release_string)
    
async def manga_string(m, release=''):

    release += 'Name: ' + \
               m.content_name

    if m.content_artists is not None:
        artists = ", ".join(m.content_artists)
        release += '\nArtists: ' + artists

    if m.magazine_text is not None:
        release += '\nMagazine: ' + m.magazine_text

    if m.content_tags is not None:
        tags = ", ".join(m.content_tags)
        release += '\nTags: ' + tags

    release += '\n' + m.content_url

    if m.store_link is not None:
        release += '\nBuy it here at: ' + m.store_link
    return release

    
async def login(username, password):
    r = requests.post('https://www.fakku.net/login/submit', data = {'username':username,'password':password})
    return r

async def get_front_page_links(soup):
    items = soup.findAll('a', class_='content-title')
    links = set()
    for manga in items:
        link = manga['href'][8:]
        links.add(link)
    return links
    
async def must_get_request(url,cookies=None, headers=None):
    while True:
        try:
            data = requests.get(url, timeout=10,cookies=cookies, headers=headers)
            data.encoding = 'utf-8'
            return data
        except:
            await asyncio.sleep(60)  # sleep to not grab a dead link over and over
            
async def fakku_script():
    await bot.wait_until_ready()  # will not begin until the bot is logged in.
    manga_set = set()
    first = True
    r  = await login(password.username, password.password)
    cookies.setCookie(r.cookies)
    print("logged in")
    while True:
        r = await must_get_request('https://fakku.net', cookies=cookies.cookies)
        soup = BeautifulSoup(r.text, 'html.parser')
        links = await get_front_page_links(soup)
        if first == True:
            manga_set = links
            first = False
        else:
            links.difference_update(manga_set)
            i = 0
            for book in links:
                i += 1
                data = await must_get_request("https://api.fakku.net/manga/"+book, cookies=cookies.cookies, headers={'Sindalf': 'True'})
                book_json = data.json()['content']
                m = manga(book_json)
                m.populate()

                html = await get_html(book_json['content_url'])  # gets the manga page
                if html is not None:
                    soup = BeautifulSoup(html, 'html.parser')  # start up html parser
                    store_link = await detect_store_link(soup)  # see if the store link exists
                    m.set_store_link(store_link)  # set store link
                    magazine_text = await detect_magazine_text(soup)  # see if the magazine link exists
                    m.set_magazine_text(magazine_text)  # set magazine link

                
                release_string = await manga_string(m, 'New Release! \n')
                await bot.send_message(bot.get_channel('196487186860867584'), release_string)  # send release details into the channel
                await bot.send_message(bot.get_channel('202830118324928512'), release_string)
                
                try:
                    data = await get_notified_users()
                    for ID in data:
                        a = {
                            'username': None,
                            'id': str(ID[0]),
                            'discriminator': None,
                            'avatar': None,
                            'bot': False
                            }
                        print(str(ID[0]))
                        try:
                            user = discord.User(**a)
                            await bot.send_message(user, release_string)
                        except Exception:
                            print("Sending failed!")
                except Exception:
                    print("Something went wrong with the sql statement!")
            if i > 0:
                msg = "Type !notify_me for PM notifications whenever a new release on FAKKU! goes up."
                await bot.send_message(bot.get_channel('196487186860867584'), msg)  # send release details into the channel
                await bot.send_message(bot.get_channel('202830118324928512'), msg)
            i = 0
            manga_set.update(links)
        await asyncio.sleep(60)

async def get_notified_users():
    cnx = mysql.connector.connect(user=password.MySQL_User, password=password.MySQL_Pass,host=password.MySQL_Host, database=password.MySQL_DB)
    cursor = cnx.cursor(buffered=True)
    query = "Select ID from releaseNotify"
    cursor.execute(query)
    data = set(cursor)
    cursor.close()    
    cnx.close()
    return data
    

@bot.command(pass_context=True, description="Use this command to receive PMs for FAKKU! releases")
async def notify_me(ctx):
    cnx = mysql.connector.connect(user=password.MySQL_User, password=password.MySQL_Pass,host=password.MySQL_Host, database=password.MySQL_DB)
    query = "Insert into releaseNotify (ID) VALUES(%s)"
    values = (ctx.message.author.id,)
    cursor = cnx.cursor(buffered=True)
    try:
        cursor.execute(query, values)
        cursor.execute('commit')
    except Exception:
        pass
    finally:
        cursor.close()
        cnx.close()
    await bot.send_message(ctx.message.author, "You will now be notified when new manga goes up on FAKKU!. Type !dont_notify_me if you want to be removed from this list.")
    
@bot.command(pass_context=True, description="Remove yourself from the FAKKU! release notification list")
async def dont_notify_me(ctx):
    cnx = mysql.connector.connect(user=password.MySQL_User, password=password.MySQL_Pass,host=password.MySQL_Host, database=password.MySQL_DB)
    query = "delete from releaseNotify where ID = %s"
    values = (ctx.message.author.id,)
    cursor = cnx.cursor(buffered=True)
    cursor.execute(query, values)
    cursor.execute('commit')
    cursor.close()
    cnx.close()
    await bot.send_message(ctx.message.author, "You have been removed from the FAKKU! notification list. Type !notify_me if you want to be readded to the notification list.")
    
    
bot.loop.set_debug(True)
bot.loop.create_task(fakku_script())
bot.run(password.Token2) # Put your own discord token here
