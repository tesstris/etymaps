# A program to plot out maps of how words evolved over time, using
# data scraped from wiktionary. By @tesstris 12/24/24.

# dependencies
# used for web scraping
import requests
import re
from bs4 import BeautifulSoup
# used for pictures
from mpl_toolkits.basemap import Basemap
import numpy as np
import matplotlib.pyplot as plt
# app gui
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QComboBox,
    QTabWidget,
    QCheckBox,
    QWidget
)
# csv handling
import csv

# Only needed for access to command line arguments
import sys

def inParenthetical(passage, word):
    word_index = passage.find(word)
    trimmed = passage[0:word_index]

    open_count = trimmed.count("(")
    closed_count = trimmed.count(")")

    return (open_count > closed_count)

        

# function getPage
# @purpose: visits the wiktionary page and parses it for paragraphs
# @parameters: language, word to search for, as strings - language should be in English,
# but word should be in the target language
# @returns: a list containing each paragraph parsed from the wiktionary page
# often this is just the etymology paragraph, but if the wiktionary page contains
# links to quotes or something, it may have grabbed those as well
def getPage(language, word):
    word = word.replace(" ", "_")

    if language != None:
        url = "https://en.wiktionary.org/wiki/" + word + "#" + language
    else:
        url = "https://en.wiktionary.org/wiki/" + word
    page = requests.get(url)
    soup = BeautifulSoup(page.content, "html.parser")
    cont = soup.find("div", attrs={"class":"mw-content-ltr mw-parser-output"})
    return cont

# function parseParagraph
# @purpose: given the body of a wiktionary article, parses it for etymology data
# @parameters: the body of a wiktionary article, returned by getPage
# @return: [desc, origins] where desc is the string describing the etymology and
# origins is a list of languages
def parseParagraph(language, etym_para, todo, data_dict):
    ety_searching = True
    lang = etym_para.findAll("div", attrs={"class":"mw-heading mw-heading2"})
    ety_index = None

    
    lang_place = None

    if language != None:
        for l in lang:
            lang_text = l.text.replace("[edit]", "")
            if lang_text == language:
                lang_place = l
                lang = lang_text
                origins = [lang_text]
                break

    if lang_place != None:
        headers = lang_place.find_all_next("h3")
        for h in headers:
            if h.text.find("Etymology") != -1:
                ety_index = h
                if h.find_previous("div", attrs={"class":"mw-heading mw-heading2"}).text.replace("[edit]", "") != lang_text:
                    #print(h.find_previous("div", attrs={"class":"mw-heading mw-heading2"}).text)
                    return None
                else:
                    break
    else:
        headers = etym_para.findAll("h3")
        for h in headers:
            if h.text.find("Etymology") != -1:
                ety_index = h
                lang = h.find_previous("div", attrs={"class":"mw-heading mw-heading2"}).text.replace("[edit]", "")
                #print(lang_text)
                origins = [lang]
                break
    

    if ety_index == None:
        return None           
    
    desc = lang + ". "
    etym_para = ety_index.find_all_next("p")
    for p in etym_para:
        etyls = p.findAll("span", attrs={"class":"etyl"})
        p = p.text
        desc += p
        prev = 0
        for etyl in etyls:
            i = p.find(etyl.text)
            period_loc = p.find(".")
            cognate_loc = p.find("Cognate")
            compare_loc = p.find("Compare")
            related_loc = p.find("Related to")
            related2_loc = p.find("related")
            cognate2_loc = p.find("cognate")



            
            # if it's not in parentheses and we've moved on to cognates, we're probably done with etymology
            # sorry this line is so long. too lazy to fix
            if (period_loc != -1 and period_loc < i) and ((cognate_loc != -1 and cognate_loc < i) or (compare_loc != -1 and compare_loc < i) or (related_loc != -1 and related_loc < i)):
                print("period break - cognate 1")
                break
            if (period_loc != -1 and period_loc < i) and ((related2_loc != -1 and related2_loc < i) or (cognate2_loc != -1 and cognate2_loc < i)):
                break

            # etymology keywords: from, of, based on
            big_from = p[0:i-1].find("From")
            little_from = p[0:i-1].find("from")
            based_on = p[0:i-1].find("based on")
            of = p[0:i-1].find("of")

            if inParenthetical(p, etyl.text):
                print(etyl.text)
                p = p[p.find(")"):-1]
                continue # if the language is between parentheses, we probably don't care about it

            if (big_from != -1 and big_from < i) or (little_from != -1 and little_from < i) or (of != -1 and of < i):
                if etyl.text not in origins:
                    if not inParenthetical(p, "from"):
                        print(p)
                        print(etyl.text, "\n")
                        origins.append(etyl.text)
                
            prev = i
            p = p[prev+len(etyl.text):-1]

        # etymology is (almost?) always contained within 1 paragraph, so once you find something, stop
        if origins != [lang]:
            break

    print(origins)
    origins_copy = origins.copy()
    for o in origins_copy:
        # make sure each language is in our dataset
        if o not in data_dict:
            # print(o)
            if o in todo:
                origins.remove(o)
                desc += "\nSorry, " + o + " isn't in our dataset yet."
            else:
                origins.remove(o)
                # print(origins_copy)

    return [desc, origins]


# function makeMap
# @purpose: plots the etymology path of a given word
# @parameters: origins, a list containing the languages in the word's etymology path, and word,
# the word being traced as a string. It only needs the word in order to give the map a title.
# @return: Either the word "Success" as a string, or, on failure, the language not found in 
# the dataset.
def makeMap(origins, word, resolution, countries):
    # this is where we do the figures!!
    plt.figure(figsize = (10,10))
    
    # using mercator projection for hashtag name brand recognition
    m = Basemap(projection='merc',llcrnrlat=-80,urcrnrlat=80,llcrnrlon=-180,urcrnrlon=180,lat_ts=20,resolution=resolution)
    m.drawcoastlines()
    
    m.fillcontinents(color='cornflowerblue',lake_color='darkblue') # choosing colors
    m.drawmapboundary(fill_color='darkblue') 

    if countries:
        m.drawcountries()
    # plot title
    plt.title(("Etymology of \"" + word + "\""))
    x1, x2, y1, y2 = 0, 0, 0, 0

    for i in range(len(origins)-1):
        # make sure each language is in our dataset
        # if origins[i] not in data_dict:
        #     if origins[i] in todo:
        #         return origins[i]
        #     else:
        #         continue
        # if origins[i+1] not in data_dict:
        #     # if not, return the Problem Language and exit the function
        #     if origins[i] in todo:
        #         return origins[i+1]
        #     else:
        #         continue

        # otherwise, use the basemap library to convert the coordinates
        # they get imported as strings so have to convert to floats first
        x1, y1 = m(float(data_dict[origins[i]][1]), float(data_dict[origins[i]][0]))
        x2, y2 = m(float(data_dict[origins[i+1]][1]), float(data_dict[origins[i+1]][0]))

        # uncomment the following line to plot the name of the language on its coords
        # plt.annotate(origins[i], xy = (x1-1000000, y1+400000+offset), bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='black'))

        # white etymology path arrows
        plt.arrow(x2, y2, x1-x2, y1-y2, color='white', linewidth=2, head_width=100000, head_length=100000, zorder = 10)

    # print(x1, y1, x2, y2)
    # some stuff to avoid messing up the original list in case we still need it
    ori_copy = origins.copy()
    ori_copy.reverse()

    # make a little legend blurb with some arrows
    desc = ""
    for i in ori_copy[0:-1]:
        desc += i + "\n↓\n"
    desc += origins[0]

    # put it on the plot
    plt.annotate(desc, xy = (x2+2000000, y2+1000000), bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='black'))


    # now we are ready
    plt.show()
    return "Success"

# function getCSV
# @description: function to load data from a csv file into a dictionary
# @param: file path to the file with the language coordinate data in it, as a string
# @return: language coordinate data as a dictionary where the format is:
# {"language": ["x", "y"]}
def getCSV(csv_file_path):
    with open(csv_file_path, 'r') as file:
        reader = csv.reader(file)
        result = {}
        for row in reader:
            key = row[0]  # First column as key
            result[key] = row[1:3]
        return result

# function entireMap
# @description: plots every single language in the dataset onto a map. functionally unusable for map purposes,
# because there's so many of them and it's so crowded, and it's also very slow
# @param: language coordinates dictionary
# @return: nothing
def entireMap(CoordsDict):
     # this is where we do the figures!!
    plt.figure(figsize = (10,10))
    # using mercator projection for hashtag name brand recognition
    m = Basemap(projection='merc',llcrnrlat=-80,urcrnrlat=80,llcrnrlon=-180,urcrnrlon=180,lat_ts=20,resolution='c')
    m.drawcoastlines()
    m.fillcontinents(color='cornflowerblue',lake_color='darkblue') # choosing colors
    m.drawmapboundary(fill_color='darkblue') 

    # plot title
    plt.title(("World Languages"))
    x1, x2, y1, y2 = 0, 0, 0, 0
    
    for i in CoordsDict:
        x1, y1 = m(float(CoordsDict[i][1]), float(CoordsDict[i][0]))
        plt.annotate(i, xy = (x1, y1), bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='black'))
    # now we are ready
    plt.show()
    return
    

# Main app gui class using PyQt6.
class MainWindow(QWidget):
    def __init__(self):
        # init the parent class
        super().__init__()

        # variables
        self.map_res = "c"
        self.countries = False
        
        # window title
        self.setWindowTitle("etymaps")
        self.bigLayout = QVBoxLayout()

        # tabs
        self.tab_widget = QTabWidget()

        self.ety_tab = QWidget()
        self.settings_tab = QWidget()
        self.about_tab = QWidget()

        # main etymology tab
        self.mainLayout = QVBoxLayout() 
        self.layout = QHBoxLayout()
        self.lang_layout = QHBoxLayout()
        
        # description where the etymology tab will go
        self.desc = QLabel("Enter a word to see its etymology.")
        self.desc.setWordWrap(True)
        self.desc.setMaximumSize(800, 500)
        
        
        text_widget = QLabel("word")
        font = text_widget.font()
        font.setPointSize(20)
        text_widget.setFont(font)

        ety_text_widget = QLabel("etymology")
        font = ety_text_widget.font()
        font.setPointSize(20)
        ety_text_widget.setFont(font)

        self.input_widget = QLineEdit()
        
        button_widget = QPushButton("go")
        button_widget.setCheckable(True)
        button_widget.clicked.connect(self.on_click_go)

        self.lang_input_widget = QLineEdit()
        text2 = QLabel("word")
        self.text3 = QLabel("language")

        self.map_button = QPushButton("Map")
        self.map_button.setCheckable(True)
        self.map_button.clicked.connect(self.on_click_map)

        self.setGeometry(100, 100, 800, 200)

        # add big "word" widget
        self.mainLayout.addWidget(text_widget)
        
        # add the language input bar
        self.lang_layout.addWidget(self.text3)
        self.lang_layout.addWidget(self.lang_input_widget)
        self.mainLayout.addLayout(self.lang_layout)
        # hidden by default
        self.lang_input_widget.hide()
        self.text3.hide()
        
        # add the word input bar
        self.layout.addWidget(text2)
        self.layout.addWidget(self.input_widget)
        self.layout.addWidget(button_widget)
        self.mainLayout.addLayout(self.layout)
        
        # add big text that says "etymology"
        self.mainLayout.addWidget(ety_text_widget)
        
        # add the etymology paragraph description widget
        self.mainLayout.addWidget(self.desc)
        self.mainLayout.addWidget(self.map_button)
        self.map_button.hide() # hidden by default until we get a mappable etymology

        self.ety_tab.setLayout(self.mainLayout)
        self.tab_widget.addTab(self.ety_tab, "etymology")

        # settings tab
        general_text = QLabel("general settings")
        font = general_text.font()
        font.setPointSize(20)
        general_text.setFont(font)

        specify_text = QLabel("Specify a language")
        specify_layout = QHBoxLayout()
        
        self.settings_layout = QVBoxLayout()
        self.language_checkbox = QCheckBox()
        self.language_checkbox.setCheckState(Qt.CheckState.Unchecked)
        self.language_checkbox.stateChanged.connect(self.lang_checkbox_click)

        self.res_dropdown = QComboBox()
        self.res_dropdown.addItem("low (recommended)")
        self.res_dropdown.addItem("medium")
        self.res_dropdown.addItem("high")
        res_text = QLabel("Map resolution")
        res_layout = QHBoxLayout()
        self.res_dropdown.currentIndexChanged.connect(self.change_res_click)

        self.countries_checkbox = QCheckBox()
        countries_text = QLabel("Draw national borders")
        self.countries_checkbox.setCheckState(Qt.CheckState.Unchecked)
        self.countries_checkbox.stateChanged.connect(self.countries_checkbox_click)
        countries_layout = QHBoxLayout()



        # self.settings_layout.addWidget(general_text)
        specify_layout.addWidget(specify_text)
        specify_layout.addWidget(self.language_checkbox)
        self.settings_layout.addLayout(specify_layout)

        res_layout.addWidget(res_text)
        res_layout.addWidget(self.res_dropdown)
        self.settings_layout.addLayout(res_layout)

        countries_layout.addWidget(countries_text)
        countries_layout.addWidget(self.countries_checkbox)
        self.settings_layout.addLayout(countries_layout)
        
        self.settings_tab.setLayout(self.settings_layout)
        self.tab_widget.addTab(self.settings_tab, "settings")
        

        # put all the tabs together
        self.bigLayout.addWidget(self.tab_widget)
        self.setLayout(self.bigLayout)

    # method for when the "go" button is clicked
    def on_click_go(self):
        
        self.word = self.input_widget.text()
        self.language = self.lang_input_widget.text()
        para = getPage(self.language, self.word)
        if para == None:
            self.desc.setText("Did not find a wiktionary page for this word.")
            return
        self.origins = parseParagraph(self.language, para, todo_dict, data_dict)
        if self.origins == None:
            self.desc.setText("Did not find an etymology section for this word. Try an alternate form?")
            return
        self.desc.setText(self.origins[0])
        
        if len(self.origins[1]) <= 1:
            self.desc.setText(self.origins[0] + "Did not parse a mappable etymology.")
            self.map_button.hide()
        else:
            self.setGeometry(100, 100, 800, 400)
            self.map_button.show()
            # map = makeMap(self.origins[1], self.word)
            # if map != "Success":
            #     self.desc.setText(self.origins[0] + "Sorry, we don't have coordinates for " + map + ".")

    # method for when the "Map" button is clicked
    def on_click_map(self):
        map = makeMap(self.origins[1], self.word, self.map_res, self.countries)
        if map != "Success":
            self.desc.setText(self.origins[0] + "Sorry, we don't have coordinates for " + map + ".")

    # method for showing and unshowing the language search bar
    def lang_checkbox_click(self, s):
        if s == 2:
            self.lang_input_widget.show()
            self.text3.show()
        else:
            self.language = None
            self.lang_input_widget.hide()
            self.text3.hide()
        return

    # method for changing the map resolution
    def change_res_click(self, index):
        if index == 0:
            self.map_res = "c"
        elif index == 1:
            self.map_res = "l"
        else:
            self.map_res = "i"

    def countries_checkbox_click(self, s):
        #blah blah
        if s == 2:
            self.countries = True
        else:
            self.countries = False
        



if __name__ == "__main__":
    # load the language dataset
    print("Loading language coordinates...")
    csv_file_path = 'language_coords.csv'
    data_dict = getCSV(csv_file_path)
    todo_dict = getCSV("diff.csv")

    print("Launching app...")
    # make the application
    app = QApplication(sys.argv)

    # window instance
    window = MainWindow()

    # show the window
    window.show()  

    # start the event loop
    app.exec()