# -*- coding: utf-8 -*-
"""
Created on Thu Aug 25 12:07:15 2016

@author: jasonweinreb
"""

import os, re, csv, nltk, datetime
import pandas as pd
import numpy as np

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from urllib.request import urlopen
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag
from unidecode import unidecode

def getPageUrl(elementLinks):
    extractLinks = []
    for element in elementLinks:
        links = element.get_attribute('href')
        extractLinks.append(links)
    return(extractLinks)

##  Import stemmers and dictionaries for stop words
snowball = nltk.stem.SnowballStemmer('english')
lancaster = nltk.stem.LancasterStemmer()
stop_words = urlopen('http://jmlr.org/papers/volume5/lewis04a/a11-smart-stop-list/english.stop').read().decode("utf-8").split("\n")
stop_words = set(stop_words)


# ==============================================================================

## Loading home URL
browser = webdriver.Firefox()
browser.get('http://markets.wsj.com/?mod=Homecle_MDW_MDC')

## Login Credentials
login = browser.find_element_by_link_text("Log In").click()
loginID = browser.find_element_by_id("username").send_keys('jweinreb')
loginPass = browser.find_element_by_id("password").send_keys('55shadow')
loginReady = browser.find_element_by_class_name("login_submit")
loginReady.submit()

## Basic search: articles containing country in the Journal since 2012 
WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.ID, "globalHatSearchInput"))
    )

search_box = browser.find_element_by_id("globalHatSearchInput")
search_box.clear()
search_box.send_keys('Malaysia') # Input search keyword
WebDriverWait(browser, 5)
search_req = browser.find_element_by_css_selector('.button-search').click()

## Close cookie policy if needed
try:
    browser.find_element_by_class_name("close").click()
except NoSuchElementException:
    print('Cookie agreement already acknowledged')
    
toggleMenu = browser.find_element_by_link_text("ADVANCED SEARCH")
toggleMenu.click()
menuOptions = browser.find_element_by_class_name('datePeriod')
browser.find_element_by_name("sfrom").send_keys("2014/08/25")
browser.find_element_by_name("sto").send_keys("2016/08/25")

## Restrict search to articles whose subject is the country:
browser.find_element_by_id('metadata').send_keys("Malaysia")

## Restrict search to articles only (exclude videos, blogs, etc)
browser.execute_script("window.scrollTo(0, 500)")
browser.find_element_by_link_text("WSJ Blogs").click()
browser.find_element_by_link_text("WSJ Videos").click()
browser.find_element_by_link_text("WSJ Site Search").click()

browser.execute_script("window.scrollTo(0, 0)")
searchArchive = browser.find_element_by_class_name('keywordSearchBar')
searchArchive.find_element_by_class_name("searchButton").click()

pageCount = browser.find_elements_by_class_name("results-count")[1].text
pageCount = int(re.sub(r'of ', '', pageCount))
resultCount = browser.find_elements_by_class_name("results-count")[0].text
resultCount = int(resultCount.rpartition("of ")[2])
# ==============================================================================


## Extract all article urls

articleLinks = []
for j in range(0, pageCount):
    elementLinks = browser.find_elements_by_xpath('//h3[@class="headline"]/a')
    links = getPageUrl(elementLinks)
    articleLinks.append(links)
    print('done with page ' + str(j+1) + ' of ' + str(pageCount))
    if j < 37:
        browser.find_element_by_class_name("next-page").click()

    
articleLinks = [y for x in articleLinks for y in x]


# Write list of urls to a csv file for later use:
with open("mys_urls.csv", "w") as csvfile:
    writer = csv.writer(csvfile, delimiter= ",")
    hdr = ['articleLink']
    writer.writerow(hdr)
    for link in articleLinks:
        entry = [link] 
        writer.writerow(entry)

os.chdir("/Users/jasonweinreb/Dropbox")
df = pd.read_csv("mys_urls.csv")

## Open WSJ homepage and log in : 
browser = webdriver.Firefox()
browser.get('http://www.wsj.com')
browser.find_element_by_class_name("close").click()

login = browser.find_element_by_link_text("Sign In").click()
loginID = browser.find_element_by_id("username").send_keys('jweinreb')
loginPass = browser.find_element_by_id("password").send_keys('55shadow')
loginReady = browser.find_element_by_class_name("login_submit")
loginReady.submit()

## Create placeholder dictionaries for Articles and Unigrams (in all articles):
Articles = {}
Unigrams = {}
article_count = 0

for i in df.articleLink[:100]:
    
    browser.get(i)
    
    # Get headline if it exists (otherwise continue) 
    try:
        headline = browser.find_element_by_class_name("wsj-article-headline").text
    except NoSuchElementException:
        print(i + ' : no headline')
        continue
    
    # Enter article headline into dictionary 
    Articles[headline] = {}
    
    # Get timestamp if it exists (otherwise continue)
    try:
        timestamp = browser.find_element_by_class_name("timestamp").text
    except NoSuchElementException:
        print(i + ' : no time stamp')
        continue 
    
    # Clean time stamp if it exists 
    timestamp = re.sub(r'Updated ', '', timestamp)
    timestamp = re.sub(r' ET', '', timestamp)
    timestamp = re.sub(r'p.m.', 'PM', timestamp)
    timestamp = re.sub(r'a.m.', 'AM', timestamp)
    if 'Sept.' in timestamp:
        timestamp = re.sub(r'Sept.', 'Sep.', timestamp)
    if "COMMENTS" in timestamp:
        timestamp = timestamp.split("\n")[0]
    if 'AM' in timestamp or 'PM' in timestamp:
        try:
            timestamp = datetime.datetime.strptime(timestamp, '%b. %d, %Y %I:%M %p')
        except ValueError:
            timestamp = datetime.datetime.strptime(timestamp, '%B %d, %Y %I:%M %p')
    else:
        try:
            timestamp = datetime.datetime.strptime(timestamp, '%B %d, %Y')
        except ValueError:
            timestamp = datetime.datetime.strptime(timestamp, '%b. %d, %Y')
    
    # Put timestamp and link into Article dictionary 
    Articles[headline]["date"] = timestamp
    Articles[headline]["link"] = i
        
    # Extract article text
    paragraphs = browser.find_elements_by_xpath('//*[@id="wsj-article-wrap"]/p')
    text = []
    for t in range(0, len(paragraphs)):
        if ('@wsj.com' not in paragraphs[t].text and 
            'contributed to this article' not in paragraphs[t].text):
            text.append(paragraphs[t].text)
    text = "".join(text)    
    text = re.sub(r'\n', ' ', text)
    text = re.sub("\W", " ", text)
    text = text.lower()
    # Tokenize, stem and remove standalone numbers and (some) proper nouns 
    tokens = nltk.word_tokenize(text)
    tokens = [snowball.stem(w) for w in tokens]
    tokens = [x for x in tokens if x not in stop_words]
    tokens = [x for x in tokens if not (x.isdigit() or x[0] == '-' and x[1:].isdigit())]
    tokens = [word for word,pos in pos_tag(tokens) if pos != "NNP"]
    
    # Add tokens to inner unigrams dictionary
    Articles[headline]["unigrams"] = {}
    for j in tokens:
        count = tokens.count(j)
        Articles[headline]["unigrams"][j] = count
        if j in Unigrams:
            Unigrams[j] += count
        else:
            Unigrams[j] = count
            
    article_count += 1            


os.chdir("/Users/jasonweinreb/Dropbox")


Articles = {k: v for k, v in Articles.items() if v}

hdr = ['headline'] + ['date'] + [unidecode(x) for x in list(Unigrams.keys())]
with open("unigrams_mys.csv", "w") as csvfile:
    writer = csv.writer(csvfile, delimiter= ",")
    writer.writerow(hdr)
    titles = list(Articles.keys())
    for i in range(0, len(titles)):
        toWrite = []
        toWrite.append(unidecode(titles[i]))
        toWrite.append(Articles[titles[i]]["date"])
        for j in list(Unigrams.keys()):
            if j in Articles[titles[i]]['unigrams']:
               toWrite.append(unidecode(str(Articles[titles[i]]["unigrams"][j])))
            else:
                toWrite.append(str(0))
        writer.writerow(toWrite)

