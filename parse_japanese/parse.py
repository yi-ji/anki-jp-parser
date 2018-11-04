#-*- coding: utf-8 -*-

import os, pickle, datetime, codecs, shutil

from aqt import mw              # Anki's main window object
from aqt.qt import *
from aqt.utils import showInfo
from anki.hooks import addHook
from anki.utils import ids2str
from anki.cards import Card
from AnkiHelper import *
from aqt.utils import showInfo
from anki.hooks import wrap
from anki.sched import Scheduler
import tempfile, os, shutil
from anki import Collection as aopen
import time
from aqt.reviewer import Reviewer
import yomi_dict
import sys, os, platform, re, subprocess, aqt.utils

JPARSER_INDEX_COUNT = 3

EXPRESSION_DECK_NAME = "Master::1Vocab::Main::JtoE"
MATCHING_FIELD = "Expression"
REFERENCE_FIELDS = ["Kana", "English", "Times"]

EXPRESSION_DECK_NAME2 = "Master::1Vocab::Main::Audio"
MATCHING_FIELD2 = "Expression"
REFERENCE_FIELDS2 = ["Kana", "English", "Times"]

EXPRESSION_DECK_NAME3 = "Master::1Vocab::Main::EtoJ"
MATCHING_FIELD3 = "Expression"
REFERENCE_FIELDS3 = ["Reading", "English", "Times"]


########################## GRAMMAR ########################################
WORD_MERGE_FILE_NAME = "textmerge.txt"
GRAMMATICAL_WORD_FIXING_RULE_NAME = "grammar.txt"
GRAMMAR_DECK_NAME = "Master::2Grammar::Grammar"
MATCHING_FIELD_GRAMMAR = "Expression"
REFERENCE_FIELDS_GRAMMAR = ["D1", "D2", "W1"]
###########################################################################

from anki.utils import stripHTML, isWin, isMac
#mecabArgs = ['--node-format=%m[%f[7]] ', '--eos-format=\n',
#            '--unk-format=%m[] ']
mecabArgs = ['-Ochasen']
kakasiArgs = ["-isjis", "-osjis", "-u", "-JH", "-KH"]

def escapeText(text):
    # strip characters that trip up kakasi/mecab
    text = text.replace("\n", " ")
    text = text.replace(u'\uff5e', "~")
    text = re.sub("<br( /)?>", "---newline---", text)
    text = stripHTML(text)
    text = text.replace("---newline---", "<br>")
    return text

if sys.platform == "win32":
    si = subprocess.STARTUPINFO()
    try:
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    except:
        si.dwFlags |= subprocess._subprocess.STARTF_USESHOWWINDOW
else:
    si = None


def mungeForPlatform(popen):
    if isWin:
        popen = [os.path.normpath(x) for x in popen]
        popen[0] += ".exe"
    elif not isMac:
        popen[0] += ".lin"
    return popen


#expr = u"カリン、自分でまいた種は自分で刈り取れ"
#print(mecab.reading(expr).encode("utf-8"))
class MecabController(object):

    def __init__(self):
        self.mecab = None
        self.kakasi = KakasiController()
        
    def setup(self):
        base = "../../addons/parse_japanese/support/"
        self.mecabCmd = mungeForPlatform(
            [base + "mecab"] + mecabArgs + [
                '-d', base, '-r', base + "mecabrc", "-u", base + "anki.dic"])
        #         [base + "mecab"] + [
        #         '-d', base])
        os.environ['DYLD_LIBRARY_PATH'] = base
        os.environ['LD_LIBRARY_PATH'] = base
        if not isWin:
            os.chmod(self.mecabCmd[0], 0o755)

    def ensureOpen(self):
        if not self.mecab:
            self.setup()
            try:
                self.mecab = subprocess.Popen(
                    self.mecabCmd, bufsize=-1, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    startupinfo=si)

            except OSError:
                raise Exception("Please ensure your Linux system has 64 bit binary support.")

    def reading(self, expr):
        self.ensureOpen()
        expr = escapeText(expr)
        self.mecab.stdin.write(expr.encode("utf-8", "ignore") + b'\n')
        #self.mecab.stdin.write(expr.encode("euc_jp", "ignore") + b'\n')
        
        self.mecab.stdin.flush()
        expr = []
        while True:
                        
            line = self.mecab.stdout.readline().rstrip(b'\r\n\t ').decode('utf-8', 'ignore')
            #line = self.mecab.stdout.readline().rstrip(b'\r\n\t ').decode('euc_jp')
            
            if not line or line == "" or line.startswith("EOS"):
                break
            expr.append(line)
        return expr
        #expr = self.mecab.stdout.readline().rstrip(b'\r\n').decode('utf-8')
        out = []
        for node in expr.split(" "):
            if not node:
                break
            (kanji, reading) = re.match("(.+)\[(.*)\]", node).groups()
            # hiragana, punctuation, not japanese, or lacking a reading
            if kanji == reading or not reading:
                out.append(kanji)
                continue
            # katakana
            if kanji == self.kakasi.reading(reading):
                out.append(kanji)
                continue
            # convert to hiragana
            reading = self.kakasi.reading(reading)
            # ended up the same
            if reading == kanji:
                out.append(kanji)
                continue
            # don't add readings of numbers
            if kanji in u"一二三四五六七八九十０１２３４５６７８９":
                out.append(kanji)
                continue
            # strip matching characters and beginning and end of reading and kanji
            # reading should always be at least as long as the kanji
            placeL = 0
            placeR = 0
            for i in range(1,len(kanji)):
                if kanji[-i] != reading[-i]:
                    break
                placeR = i
            for i in range(0,len(kanji)-1):
                if kanji[i] != reading[i]:
                    break
                placeL = i+1
            if placeL == 0:
                if placeR == 0:
                    out.append(" %s[%s]" % (kanji, reading))
                else:
                    out.append(" %s[%s]%s" % (
                        kanji[:-placeR], reading[:-placeR], reading[-placeR:]))
            else:
                if placeR == 0:
                    out.append("%s %s[%s]" % (
                        reading[:placeL], kanji[placeL:], reading[placeL:]))
                else:
                    out.append("%s %s[%s]%s" % (
                        reading[:placeL], kanji[placeL:-placeR],
                        reading[placeL:-placeR], reading[-placeR:]))
        fin = u""
        for c, s in enumerate(out):
            if c < len(out) - 1 and re.match("^[A-Za-z0-9]+$", out[c+1]):
                s += " "
            fin += s
        return fin.strip().replace("< br>", "<br>")

class KakasiController(object):

    def __init__(self):
        self.kakasi = None

    def setup(self):
        base = "../../addons/parse_japanese/support/"
        self.kakasiCmd = mungeForPlatform(
            [base + "kakasi"] + kakasiArgs)
        os.environ['ITAIJIDICT'] = base + "itaijidict"
        os.environ['KANWADICT'] = base + "kanwadict"
        if not isWin:
            os.chmod(self.kakasiCmd[0], 0o755)

    def ensureOpen(self):
        if not self.kakasi:
            self.setup()
            try:
                self.kakasi = subprocess.Popen(
                    self.kakasiCmd, bufsize=-1, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    startupinfo=si)
            except OSError:
                raise Exception("Please install kakasi")

    def reading(self, expr):
        self.ensureOpen()
        expr = escapeText(expr)
        self.kakasi.stdin.write(expr.encode("sjis", "ignore") + b'\n')
        self.kakasi.stdin.flush()
        res = self.kakasi.stdout.readline().rstrip(b'\r\n').decode("sjis")
        return res


class MecabElement:
    def __init__(self, word, origin, pos, pos_detail, reading = None):
        self.word = word
        self.origin = origin
        self.pos = pos
        self.pos_detail = pos_detail
        self.reading = reading

    def __isStringMatched(self, expr_element, expr_other):
        if expr_element == '*':
            return True
        return (expr_element == expr_other)

    def isMatched(self, element):
        word = element.word
        origin = element.origin
        pos = element.pos
        pos_detail = element.pos_detail
        return self.__isStringMatched(self.word, word) and self.__isStringMatched(self.origin, origin) and self.__isStringMatched(self.pos, pos) \
                and self.__isStringMatched(self.pos_detail, pos_detail) 

    def printContent(self):
        log("[%s, %s, %s, %s, %s]" % (self.word, self.reading, self.origin, self.pos, self.pos_detail))

class MecabElementSequence:
    def __init__(self, line):
        self.__load(line)

    def __load(self, line):
        items = line.split('+')
        self.sequence = []
        for item in items:
            content = re.match("\[(.+)\]", item).groups()
            #log(content[0])
            content = content[0].split(',')
            elem = MecabElement(content[0].strip(), content[1].strip(), content[2].strip(), content[3].strip())
            self.sequence.append(elem)
    
    @staticmethod        
    def convertToElementSequence(contents):
        elements = []
        for word_items in contents:
            word_items_line = word_items.strip(' \t\n\r')
            if not word_items_line or word_items_line == "":
               continue
            item = word_items_line.split(u"\t")
            word = item[0]
            reading = item[1]
            origin = item[2]
            pos, pos_detail = u"N/A", None
            if len(item) >= 4:
                pos = item[3]
                if len(item) >= 5:
                    pos_detail = item[4]
            elements.append(MecabElement(word, origin, pos, pos_detail, reading))
        return elements
            
    def getLength(self):
        return len(self.sequence)

    def isMatched(self, sequence):
        try:
            for i in range(self.getLength()):
                if not self.__getElement(i).isMatched(sequence[i]):
                    return False
        except Exception as e:
            log("len =%d&%d i = %d sequence=%d" % (self.getLength(), len(self.sequence), i, len(sequence)))
            log(e)
            raise(e)

        return True

    def __getElement(self, idx):
        return self.sequence[idx]

    def printContent(self):
        self.sequence[0].printContent()
        for i in range(1,self.getLength()):
            log("+")
            self.sequence[i].printContent()
            
class WordMergeRule:
    def __init__(self, line):
        
        sides = line.split('=')
        self.left = MecabElementSequence(sides[0].strip())
        #log("**WordMergeRule**")
        #log(sides[0])
        #log(sides[1])

        content = re.match("\[(.+)\]", sides[1].strip()).groups()
        #log(content[0])
        content = content[0].split(',')
        self.right = MecabElement(content[0].strip(), content[1].strip(), content[2].strip(), content[3].strip())
        #self.left.printContent()
        #self.right.printContent()

    def convert(self, sequence):
        
        rule_len = self.left.getLength()
        while(True):
            
            #log("seq_len=%d rule_len=%d" % (len(sequence), rule_len))
            matched = False
            i = 0
            while i in range(len(sequence) - rule_len + 1):
                sub_seq = sequence[i:i+rule_len]
                #log("before i=%d len=%d rul_len=%d" % (i, len(sequence), rule_len))
                if self.left.isMatched(sub_seq):
                    del sequence[i:i+rule_len]
                    #log("after=%d" % len(sequence))
                    sequence.insert(i, self.right)
                    matched = True
                    break
                i += 1
            if matched == False:
                break              
        return sequence
    def printContent(self):
        self.left.printContent()
        log("=")
        self.right.printContent()
        print()

class WordMergeRuleSet:
    def __init__(self, filename):
        self.rules = None
        try:
            with open(filename, 'rb') as f:
                content = f.read().decode('euc_jp')
                content = content.split('\r\n')
                #log("***WordMergeRuleSet***")
                #log(content)
                rules = []
                #log("len=%d" % (len(content)))
                for i in range(len(content)):
                    #log("WordMergeRule %d" % (i + 1))
                    #log(content[i])
                    if content[i].strip() == '':
                        continue
                    rules.append(WordMergeRule(content[i].strip()))
                    
                self.rules = rules
                #log("WordMergeRule loading finished!")

        except Exception as e:
            log("**WordMergeRule Exception**")
            log(e)

    def convert(self, sequence):
        if not self.rules:
            log("There is no word merge rules!")
            return sequence
        for rule in self.rules:
            sequence = rule.convert(sequence)
        return sequence

    def printContent(self):
        for rule in self.rules:
            rule.printContent()
    

class GrammaticalWordFixingRule:
    def __init__(self, line):
        #log("**Load GrammaticalWordFixingRule**")
        #log(line)
        sides = line.split('=')
        self.left = MecabElementSequence(sides[0].strip())
        if len(sides) == 3:
            content = re.match("\[(.+)\]", sides[2].strip()).groups()[0].split(',')
            self.right = MecabElement(content[0].strip(), content[1].strip(), content[2].strip(), content[3].strip())
            
            self.middle = MecabElementSequence(sides[1].strip())
        else:
            content = re.match("\[(.+)\]", sides[1].strip()).groups()[0].split(',')
            self.right = MecabElement(content[0].strip(), content[1].strip(), content[2].strip(), content[3].strip())

    def convert(self, sequence):
        seq_len = len(sequence)
        rule_len = self.left.getLength()
        middle_rule_len = self.middle.getLength()
        diff_len = middle_rule_len - rule_len
        while(True):
            matched = False
            i = 0
            while i in range(len(sequence) - rule_len + 1):
                sub_seq = sequence[i:i+rule_len]
                if (not self.middle and self.left.isMatched(sub_seq)) or (self.middle and i >= diff_len and self.middle.isMatched(sequence[i - diff_len: i + rule_len])):
                    del sequence[i:i+rule_len]
                    sequence.insert(i, self.right)
                    matched = True
                    break
                i += 1
            if matched == False:
                break
            
            
        return sequence

    def printContent(self):
        self.left.printContent()
        log("=")
        if self.middle:
            self.middle.printContent()
        self.right.printContent()
        log("")

class GrammaticalWordFixingRuleSet:
    def __init__(self, filename):
        self.rules = None
        try:
            with open(filename, 'rb') as f:
                content = f.read().decode('euc_jp')
                content = content.split('\r\n')
                
                rules = []
                for i in range(len(content)):
                    if content[i].strip() == '':
                        continue
                    rules.append(GrammaticalWordFixingRule(content[i].strip()))
                    
                self.rules = rules
                #log("***GrammaticalWordFixingRuleSet***")
                #log(content)
                
        except Exception as e:
            log("**GrammaticalWordFixingRule Exception**")
            log(e)

    def convert(self, sequence):
        if not self.rules:
            log("There is no grammatical word fixing rules!")
            return sequence
        for rule in self.rules:
            sequence = rule.convert(sequence)
        return sequence

    def printContent(self):
        for rule in self.rules:
            rule.printContent()
            log("")

class Parser:
    
    __CssClassOfDueKanji = "due"
    __CssClassOfNotDueKanji = "not-due"
    __CssClassOfSuspendedKanji = "suspended"
    __CssClassOfUnknownKanji = 'jparser-missing'
    
    def load(self):

        log("Load Plugin\n")
        
        self.__setupObjectData()
        self.__loadDict()
        self.__addCSS()
        self.__addHooks()
        self.__loadMecab()

        log("End Load Plugin\n")

    def __addCSS(self):
        
        Parser.css = self.loadCss()
        Parser.oldCss = Card.css
        Card.css = injectCss

    def __addHooks(self):
              
        addHook('fmod_jparser', self.injectParser)
        addHook('fmod_jparser2', self.injectParser2)
        addHook('fmod_jparser3', self.injectParser3)
        addHook("showAnswer", self.showAnswer) 
       
    def __loadMecab(self):
        self.mecab = MecabController()
        self.mecab.setup()
        self.mecab.ensureOpen()
        
        

    def __setupObjectData(self):
        
        self.cssFileInPlugin  = os.path.join(mw.pm.addonFolder(), 'parse_japanese', 'styles-jparser.css')
 
    def __loadDictFromDeck(self, deck_name, match_field, ref_fields):

        deckID = mw.col.decks.byName(deck_name)["id"]
        wholeCards = AnkiHelper.getCards(deckID)
        my_dict = {}
        for card in wholeCards:
            note = card.note
            ref_note = []
            for field in ref_fields:
                ref_note.append(note[field])

            my_dict[note[match_field]] = (tuple(ref_note), (card.ivl, card.queue, card.due, card.id, card.odid, card.type))
        return my_dict

    def __loadDict(self):

        self.dictYomi = yomi_dict.initLanguage()

        self.dict = []
        self.dict.append(self.__loadDictFromDeck(EXPRESSION_DECK_NAME, MATCHING_FIELD, REFERENCE_FIELDS))
        if JPARSER_INDEX_COUNT > 1:
            self.dict.append(self.__loadDictFromDeck(EXPRESSION_DECK_NAME2, MATCHING_FIELD2, REFERENCE_FIELDS2))
            self.dict.append(self.__loadDictFromDeck(EXPRESSION_DECK_NAME3, MATCHING_FIELD3, REFERENCE_FIELDS3))
        self.indexGrammarDict = len(self.dict)
        self.dict.append(self.__loadDictFromDeck(GRAMMAR_DECK_NAME, MATCHING_FIELD_GRAMMAR, REFERENCE_FIELDS_GRAMMAR))

        self.__loadWordMergeFile()
        self.__loadGrammaticalWordFixingRuleFile()

    def __loadWordMergeFile(self):

        path = os.path.join(mw.pm.addonFolder(), 'parse_japanese', WORD_MERGE_FILE_NAME)
        self.ruleSetWordMerge = WordMergeRuleSet(path)

    def __loadGrammaticalWordFixingRuleFile(self):
        path = os.path.join(mw.pm.addonFolder(), 'parse_japanese', GRAMMATICAL_WORD_FIXING_RULE_NAME)
        self.ruleSetGrammaticalWordFixing = GrammaticalWordFixingRuleSet(path)

    def getMatchingField(self, index):
        if index == 0:
            return MATCHING_FIELD
        elif index == 1:
            return MATCHING_FIELD2
        elif index == 2:
            return MATCHING_FIELD3
        elif index == 3:
            return MATCHING_FIELD_GRAMMAR    

    def getReferenceFields(self, index):
        if index == 0:
            return REFERENCE_FIELDS
        elif index == 1:
            return REFERENCE_FIELDS2
        elif index == 2:
            return REFERENCE_FIELDS3
        elif index == 3:
            return REFERENCE_FIELDS_GRAMMAR
     
    def loadCss(self):
        #log("*** loadCss function ***")
        try:
            #log(self.cssFileInPlugin)
            f = open(self.cssFileInPlugin, 'r')
            #log(f.read())
            css = unicode(f.read(), 'utf-8')
            f.close()
            
        except Exception as e:
            log(e)
            css = u''
        return css

    def unload(self):
        Card.css = Parser.oldCss

    
    def nextDue(self, odid, queue, due, type): #get next due of the card
        if odid:
            return 0
        elif queue == 1:
            date = due
        elif queue == 0 or type == 0:
            return due
        elif queue in (2,3) or (type == 2 and queue < 0):
            date = time.time() + ((due - mw.col.sched.today)*86400)
        else:
            return 0
        return time.strftime("%Y-%m-%d", time.localtime(date))

    def showAnswer(self):
        log("show answer pressed!")

        if hasattr(self, 'modifiedItems'):
            for key, value in self.modifiedItems.iteritems():
                jsFunction = "changeStateJParser('%s', %d);" %(key, value)
                mw.web.eval(jsFunction)
        
    def getJavaScriptFunctionJParser(self):
            
            return  '''<div><script>
                    function onMouseDownCharJParser(event, kanji, idx)
                    {   
                        var elements = document.getElementsByClassName(kanji);
                        var isSuspended = pluginObjectJParser.isSuspended(kanji, idx);
                        
                        for(var i = elements.length - 1; i >= 0; --i)
                        {
                      
                            if(isSuspended)
                            {
                                //alert("currently suspended");
                                pluginObjectJParser.modifyKanji(kanji, idx);
                                pluginObjectJParser.updateDict(kanji, idx);
                                elements[i].classList.remove("suspended");
                                elements[i].classList.add("due");
   
                            }
                            else{
                                
                                var isDue = pluginObjectJParser.isDue(kanji, idx);
                                //alert(kanji + ' ' + idx + "  " + isDue);
                                if(isDue){
                                   
                                   if(event.button == 0)
                                   {
                                        onGoodButtonDirectClickedJParser(kanji, idx);
                                   }
                                   else
                                   {
                                       var modal_body = pluginObjectJParser.getReviewWindow(kanji, idx);
                                       document.getElementById("myModalBody").innerHTML = modal_body;

                                      
                                       var modal = document.getElementById("myModal");
                                       modal.style.display = "block";

                                       var span = document.getElementsByClassName("close")[0];
                                       span.onclick = function() {
                                              modal.style.display = "none";
                                       }
                                       window.onclick = function(event) {
                                          if (event.target == modal) {
                                              modal.style.display = "none";
                                          }
                                       }
                                   }

                                   
                                }    
                                
                            }
                            
                        }
                            
                    }
                    
                    function changeStateJParser(kanji, value)
                    {

                            var elements = document.getElementsByClassName(kanji);
                            if(value == 2)
                            {
                                for(var i = elements.length - 1; i >= 0; --i)
                                {
                                    contents = elements[i].innerHTML;
                                    var right_end = "jparser-not-right-end";
                                    if(elements[i].className.indexOf("jparser-right-end") !== -1) 
                                        right_end = "jparser-right-end";
                                    elements[i].outerHTML = "<a style= 'text-decoration:none;' href='http://tangorin.com/general/" + kanji + "'><span class='" + kanji + " " + right_end + " jparser not-due'>" + contents + "</span></a>"
                                }
                            }
                            else
                            {

                                for(var i = elements.length - 1; i >= 0; --i)
                                {
                              
                                    elements[i].classList.remove("suspended");
                                    elements[i].classList.add("due");
                                }
                            }
                    }
                    </script></div>'''
    def getModalScriptJParser(self):
            return '''
                    <div>
                        <script>
                        function onGoodButtonDirectClickedJParser(kanji, idx)
                        {
                            pluginObjectJParser.setCurrentCard(kanji, idx)
                            onButtonClickedJParser(kanji, 2, idx)
                            //alert("left clicked");  
                        }

                        function onButtonClickedJParser(kanji, ease, idx)
                        {
                            //alert(kanji + " " + idx + " " + ease);
                            pluginObjectJParser.rescheduleCard(ease);
                            pluginObjectJParser.updateDict(kanji, idx);
                            
                            var isDue = pluginObjectJParser.isDue(kanji, idx);
                            if(!isDue)
                            {
                                var elements = document.getElementsByClassName(kanji);
                                for(var i = elements.length - 1; i >= 0; --i)
                                {
                                    contents = elements[i].innerHTML
                                    var right_end = "jparser-not-right-end";
                                    if(elements[i].className.indexOf("jparser-right-end") !== -1) 
                                        right_end = "jparser-right-end";

                                    elements[i].outerHTML = "<a style= 'text-decoration:none;' href='http://tangorin.com/general/" + kanji + "'><span class='" + kanji + " " + right_end + " jparser not-due'>" + contents + "</span></a>"
                                }
                            }
                            var modal = document.getElementById("myModal");
                            modal.style.display = "none";
                            
                        }
                        </script>    
                    </div>
                    <div id="myModal" class="modal">
                            <div class="modal-content">
                                <div class="modal-header">
                                  <span class="close">&times;</span>
                                  
                                </div>
                                <div id="myModalBody" class="modal-body">
                                </div>
                            </div>
                    </div>'''

    def getRemap(self, txt, index):

            txt = txt.replace("<br>", "")
            current_date = datetime.datetime.today().strftime('%Y-%m-%d')
            self.modifiedItems = {}
            log("** sentences **")
            log(txt)

            txts = re.split('<br +/>', txt)
            log("sent count = %d" %(len(txts)))
            for txt in txts:

                word_items = self.mecab.reading(txt)
                                       
                
                
                line_max_len = 34
                line_offset = 20
                current_len = 0

                self.ruleSetWordMerge.printContent()
                #self.ruleSetGrammaticalWordFixing.printContent()

                word_items = MecabElementSequence.convertToElementSequence(word_items)
                word_items = self.ruleSetWordMerge.convert(word_items)
                word_items = self.ruleSetGrammaticalWordFixing.convert(word_items)

                log("***after applying rules***")
                for item in word_items:
                    item.printContent()
                log("")

                yield('<div>')
                for i in range(len(word_items)):
                                   
                    word = word_items[i].word
                    reading_moph = word_items[i].reading
                    origin_word = word_items[i].origin
                    
                    
                    linkUrl = "http://tangorin.com/general/%s" % (origin_word)

                    table = ""
                    

                    if (origin_word in self.getDict(index)) or (origin_word in self.getDict(self.indexGrammarDict)):

                        idx = index
                        if origin_word in self.getDict(self.indexGrammarDict):
                            idx = self.indexGrammarDict

                        (ref_note, ref_card) = self.getDict(idx)[origin_word]

                        (ivl, queue, due, id, odid, type) = ref_card
                        
                        table = "<table>"
                        table += "<p>" + origin_word + "</p>"
                        for item in ref_note:
                            table += "<p>" + item + "</p>"
                        table += "</table>"


                        next_date = self.nextDue(odid, queue, due, type)
                        not_due = False
                        if queue == -1:
                            classs = self.__CssClassOfSuspendedKanji
                        elif isinstance(next_date, (int, long)) or next_date <= current_date:
                            classs = self.__CssClassOfDueKanji
                        else:
                            classs = self.__CssClassOfNotDueKanji
                            not_due = True

                        if current_len % line_max_len > line_max_len - line_offset:
                            classs += " jparser-right-end"
                        else:
                            classs += " jparser-not-right-end"
            
                        jsfunction = "javascript:onMouseDownCharJParser(event, '%s', %d);" % (origin_word, idx)
                                                 
                        if not_due:
                             res = '<a style="text-decoration:none;" href="%s"><span class="%s jparser %s">%s<span>%s</span></span></a>' % (linkUrl, origin_word, classs, word, table)
                        else:                               
                             res = '<span class="%s jparser %s" onmousedown= "%s">%s<span>%s</span></span>' % (origin_word, classs, jsfunction, word, table)
            
                        yield res
             
                    else:

                        classs = self.__CssClassOfUnknownKanji
                        if current_len % line_max_len > line_max_len - line_offset:
                            classs += " jparser-right-end"
                        else:
                            classs += " jparser-not-right-end"
                        
                        if origin_word:
                            table = "<p>" + origin_word + "</p>"

                        if reading_moph:
                            table += "<p>" + reading_moph + "</p>"
                        
                        linkUrl = "http://tangorin.com/general/%s" % (origin_word)
                        meanings = self.dictYomi.findTerm(origin_word)
                        if meanings and meanings[1]>0:
                            meaning = meanings[0][0]
                            #table += "<p>" + meaning['reading'] + "</p>"
                            #meaning['source']+'","'+meaning['reading']
                            mat = re.match("(\([^\(\)]+\))(.+)(\([^\(\)]+\))", meaning['glossary'])
                            middle = meaning['glossary']
                            if mat != None:
                                (front, middle, back) = mat.groups()
                            #table += "<p>" + meaning['glossary'] + "</p>"
                            table += "<p>" + middle + "</p>"
                        
                        if table != "":
                            table = "<table>" + table + "</table>"
                            res = '<a style="text-decoration:none;" href="%s"><span class="%s">%s<span>%s</span></span></a>' % (linkUrl, classs, word, table)
                        else:
                            res = '<a style="text-decoration:none;" href="%s"><span class="%s">%s</span></a>' % (linkUrl, classs, word)
                                                
                        yield(res)
                        
                    current_len += len(word)
                yield('</div>''<div><br /></div>')

    def injectParser(self, txt, *args):
        
        def remap():
            return self.getRemap(txt, 0)    
             
        src =  self.getJavaScriptFunctionJParser() + self.getModalScriptJParser() + ''.join([x for x in remap()])
        #log(src)
        return src

    def injectParser2(self, txt, *args):
        
        def remap():
            return self.getRemap(txt, 1)    
             
        src =  self.getJavaScriptFunctionJParser() + self.getModalScriptJParser() + ''.join([x for x in remap()])
        #log(src)
        return src

    def injectParser3(self, txt, *args):
        
        def remap():
            return self.getRemap(txt, 2)    
             
        src =  self.getJavaScriptFunctionJParser() + self.getModalScriptJParser() + ''.join([x for x in remap()])
        #log(src)
        return src

    def getDict(self, idx):
        return self.dict[idx]

    def updateDict(self, note, card, index):
        mydict = self.getDict(index)
        matching_field = self.getMatchingField(index)
        reference_fields = self.getReferenceFields(index)
        ref_note = []
        for field in reference_fields:
            ref_note.append(note[field])
        mydict[note[matching_field]] = (tuple(ref_note), (card.ivl, card.queue, card.due, card.id, card.odid, card.type))

class JSObjectJParser(QObject):

    def __init__(self, parser):
        super(JSObjectJParser, self).__init__()
        self.parser = parser
        self.master = ""
        
    def getDictData(self, kanji, idx):
        log("***jsObjectJParser getDictData***")
        log("idx = %d" % idx)
        log(kanji)
        return self.parser.getDict(idx)[kanji]
         

    def nextDue(self, odid, queue, due, type): #get next due of the card
        if odid:
            return 0
        elif queue == 1:
            date = due
        elif queue == 0 or type == 0:
            return due
        elif queue in (2,3) or (type == 2 and queue < 0):
            date = time.time() + ((due - mw.col.sched.today)*86400)
        else:
            return 0
        return time.strftime("%Y-%m-%d", time.localtime(date))

    def getKanjiKind(self, odid, queue, due, type):

        current_date = datetime.datetime.today().strftime('%Y-%m-%d')
        next_date = self.nextDue(odid, queue, due, type)
        if queue == -1: #suspended
            return 0
        elif isinstance(next_date, (int, long)) or next_date <= current_date: #due
            return 1
        else: #not-due
            return 2

    def suspendCards(self, ids):
        "Suspend cards."
        
        mw.col.sched.suspendCards(ids)
        mw.col.reset()

    def unsuspendCards(self, ids):
        "Unsuspend cards."
        
        mw.col.sched.unsuspendCards(ids)
        mw.col.reset()
    

    @pyqtSlot(int)
    def rescheduleCard(self, ease):
        log("reschedule card")
      
        mw.col.sched.answerCard(self.card, int(ease))
     

    @pyqtSlot(str, int)
    def modifyKanji(self, kanji, idx):

        current_date = datetime.datetime.today().strftime('%Y-%m-%d')
        (_ , ref_card) = self.getDictData(kanji, idx)
        (ivl, queue, due, id, odid, type) = ref_card

        due_date = self.nextDue(odid, queue, due, type)
        log("modify kanji");
        if queue == -1: #suspended kanji to due
            self.unsuspendCards([id])
            #log("set due = {} kanji={}".format(mw.col.sched.today, self.kanjiDict.singleKanjiDict.get(kanji)))
            AnkiHelper.setDue(mw.col.sched.today, id)
            #log("modify kanji-unsuspend");
        elif isinstance(due_date, (int, long)) or due_date <= current_date: #due 
            pass
        else: #not due kanji to suspend
            log("modify kanji-suspend");
            self.suspendCards([id])

    @pyqtSlot(str, int, result=bool)
    def isSuspended(self, kanji, idx):
        
        (_ , ref_card) = self.getDictData(kanji, idx)
        (ivl, queue, due, id, odid, type) = ref_card
        return queue == -1

    @pyqtSlot(str, int, result=bool)
    def isDue(self, kanji, idx):

        #log("isDue idx = %d" %(idx))
        #log(kanji)
        (_ , ref_card) = self.getDictData(kanji, idx)
        (ivl, queue, due, id, odid, type) = ref_card
        current_date = datetime.datetime.today().strftime('%Y-%m-%d')
        due_date = self.nextDue(odid, queue, due, type)
        #log("next_due = {} kanji={} trueorfalse={} due_date<".format(due_date, self.kanjiDict.singleKanjiDict.get(kanji), isinstance(due_date, (int, long)), due_date <= current_date))

        if isinstance(due_date, (int, long)) or due_date <= current_date:
            return True
        else:
            return False

    @pyqtSlot(str, int)
    def updateDict(self, kanji, idx):
        
        (_ , ref_card) = self.getDictData(kanji, idx)
        (ivl, queue, due, id, odid, type) = ref_card

        origin_kind = self.getKanjiKind(odid, queue, due, type)

        card = AnkiHelper.getCardById(id)
        note = card.note
        self.parser.updateDict(note, card, idx)        
        new_kind = self.getKanjiKind(card.odid, card.queue, card.due, card.type)

        if origin_kind != new_kind:
           self.parser.modifiedItems[kanji] = new_kind

    def _defaultEase(self, card):
        if mw.col.sched.answerButtons(card) == 4:
            return 3
        else:
            return 2        

    def _answerButtonList(self, card):
        l = ((1, _("Again")),)
        cnt = mw.col.sched.answerButtons(card)
        if cnt == 2:
            return l + ((2, _("Good")),)
        elif cnt == 3:
            return l + ((2, _("Good")), (3, _("Easy")))
        else:
            return l + ((2, _("Hard")), (3, _("Good")), (4, _("Easy")))                 
    
    def _buttonTime(self, i, card):
        if not mw.col.conf['estTimes']:
            return "<div class=spacer></div>"
        txt = mw.col.sched.nextIvlStr(card, i, True) or "&nbsp;"
        return '<span class=nobold>%s</span><br>' % txt

    def _answerButtons(self, card, kanji, idx):
        default = self._defaultEase(card)
        def but(i, label):
            if i == default:
                extra = "id=defease"
            else:
                extra = ""
            due = self._buttonTime(i, card)
            #log("due={} label={}".format(due, label))
            return '''
            <td align=center>%s<button %s title="%s" 
            onclick="javascript:onButtonClickedJParser('%s', '%s', %d);">%s</button></td>''' % (due, extra, _("Shortcut key: %s") % i, kanji, i, idx, label)

        buf = "<center><table cellpading=0 cellspacing=10><tr>"
        for ease, label in self._answerButtonList(card):
            buf += but(ease, label)
        buf += "</tr></table>"
        script = """
<script>$(function(){$("#defease").focus();});</script>"""
        #log(buf+script)
        return buf + script


    @pyqtSlot(str, int, result = str)
    def getReviewWindow(self, kanji, idx):
        (_ , ref_card) = self.getDictData(kanji, idx)
        (ivl, queue, due, id, odid, type) = ref_card
        
        self.card = Card(mw.col, id)
        self.card.startTimer()
        note = self.card.note()
        #log("card={} note={}".format(card, note)) 
        scpt = self._answerButtons(self.card, kanji, idx)
        #log(scpt)
        return scpt
    
    @pyqtSlot(str, int)
    def setCurrentCard(self, kanji, idx):
        (_ , ref_card) = self.getDictData(kanji, idx)
        (ivl, queue, due, id, odid, type) = ref_card
        self.card = Card(mw.col, id)
        self.card.startTimer()

def injectCss(self):
    return '<style>%s</style>' % Parser.css + Parser.oldCss(self)

def log(msg):
    logPath = os.path.join(mw.pm.addonFolder(), 'parse_japanese', 'parse_japanese.log')
    txt = '%s: %s' % (datetime.datetime.now(), msg)
    f = codecs.open(logPath, 'a', 'utf-8')
    f.write(txt + '\n')
    #f.write(txt)
    f.close()


kanji = Parser()

jsObjectJParser = JSObjectJParser(kanji)
flag = None

def _initWeb():
    global flag
    flag = True

def _showQuestion():
    global jsObjectJParser, flag
    if flag:
        flag = False
        mw.web.page().mainFrame().addToJavaScriptWindowObject("pluginObjectJParser", jsObjectJParser)

mw.reviewer._initWeb=wrap(mw.reviewer._initWeb,_initWeb,"before")
mw.reviewer._showQuestion=wrap(mw.reviewer._showQuestion,_showQuestion,"before")


#addHook("profileLoaded", addToMenuBar)
addHook("profileLoaded", kanji.load)
addHook("unloadProfile", kanji.unload)

action_label = "Reload Parser"
action = None
for a in mw.form.menuTools.actions():
    if a.text() == action_label:
        action = a

if action:
    action.triggered.disconnect()
else:
    action = QAction(action_label, mw)
    mw.form.menuTools.addAction(action)
action.triggered.connect(kanji.load)
