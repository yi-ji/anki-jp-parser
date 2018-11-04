
from aqt import mw

from anki.utils import joinFields, splitFields

class AnkiCard:
    def __init__(self, ivl, queue, due, id, odid, type):
        self.ivl = ivl
        self.queue = queue
        self.due = due
        self.id = id
        self.odid = odid
        self.type = type
        
class AnkiNote:
    def __init__(self, id, fields, mid):
        self.id = id
        
        self.fields = splitFields(fields)
        self._model = mw.col.models.get(mid)
        self._fmap = mw.col.models.fieldMap(self._model)
           
    # Dict interface
    ##################################################

    def keys(self):
        return self._fmap.keys()

    def values(self):
        return self.fields

    def items(self):
        return [(f['name'], self.fields[ord])
                for ord, f in sorted(self._fmap.values())]

    def _fieldOrd(self, key):
        try:
            return self._fmap[key][0]
        except:
            raise KeyError(key)

    def __getitem__(self, key):
        return self.fields[self._fieldOrd(key)]

    def __setitem__(self, key, value):
        self.fields[self._fieldOrd(key)] = value

class AnkiHelper:

    #get cards for expressions
    
    @staticmethod
    def getCardInfo(deck_id, main_field, expressions):

        result_cards_count = len(expressions)
        result_cards = [None] * result_cards_count
        count = 0
        for card in cards:
            note = card.note
            if note[main_field] in expressions:
                index = expressions.index(note[main_field])
                result_cards[index] = card
                count += 1
                if count == result_cards_count:
                    break
        return result_cards
    
    @staticmethod
    def setQueue(queue, id): 
         rv = mw.col.db.all("Update cards set queue= ? Where id = ?", queue, id)
    
    @staticmethod
    def setDue(due, id): 
         rv = mw.col.db.all("Update cards set due= ? Where id = ?", due, id)

    @staticmethod
    def setQueueAndDue(queue, due, id): 
         rv = mw.col.db.all("Update cards set queue= ? type=? due=? Where id = ?", queue, queue, due, id)

    @staticmethod
    def getCards(did):
        
        rows = mw.col.db.all("Select c.ivl, n.id, n.flds, n.mid, c.queue, c.due, c.id, c.odid, c.type from cards c, notes n "
                             "Where c.nid = n.id and c.did = ?", did)
        ankiCards = list()
        for row in rows:
            ankiCard = AnkiCard(row[0], row[4], row[5], row[6], row[7], row[8])
            ankiCard.note = AnkiNote(row[1], row[2], row[3])
            ankiCards.append(ankiCard)

        return ankiCards

    @staticmethod
    def getCardById(id):
        
        rows = mw.col.db.all("Select c.ivl, n.id, n.flds, n.mid, c.queue, c.due, c.id, c.odid, c.type from cards c, notes n "
                             "Where c.nid = n.id and c.id = ?", id)
        ankiCards = list()
        for row in rows:
            ankiCard = AnkiCard(row[0], row[4], row[5], row[6], row[7], row[8])
            ankiCard.note = AnkiNote(row[1], row[2], row[3])
            ankiCards.append(ankiCard)

        return ankiCards[0]    
    #@staticmethod
    #def getKanjiInfo(kanji) #to get expression, kana, english info including kanji

    @staticmethod
    def getCardsByNoteType(noteType): #noteType:string

        noteTypeId = AnkiHelper.getNoteTypeId(noteType)

        rows = mw.col.db.all("Select c.ivl, n.id, n.flds, n.mid, c.queue, c.due, c.id, c.odid, c.type  from cards c, notes n "
                             "Where c.nid = n.id and n.mid = ?", noteTypeId)

        ankiCards = list()
        for row in rows:
            
            ankiCard = AnkiCard(row[0], row[4], row[5], row[6], row[7], row[8])
            ankiCard.note = AnkiNote(row[1], row[2], row[3])
            ankiCards.append(ankiCard)

        return ankiCards

    @staticmethod
    def getNoteTypes():
        model_names = []
        model_ids = [int(id) for id in mw.col.models.ids()]
        for model_id in model_ids:
            model = mw.col.models.get(model_id)
            model_name = model["name"]
            model_names.append(model_name)
        return model_names

    @staticmethod
    def getNoteTypeId(noteType):
        model_ids = [int(id) for id in mw.col.models.ids()]
        for model_id in model_ids:
            model = mw.col.models.get(model_id)
            model_name = model["name"]
            if model_name == noteType:
                return model_id
        return None

    @staticmethod
    def isDeckModified(dlmod, nlmod, clmod, deck):
        if dlmod != deck["mod"]:
            return True
        did = deck["id"]
        return mw.col.db.first("select * From Notes n, Cards c "
            "where c.nid = n.id and (n.mod > ? or c.mod > ?) and c.did = ? limit 1", nlmod, clmod, did) != None
    
    @staticmethod
    def getLastModified(did):
        maxes = mw.col.db.first("Select max(n.mod), max(c.mod) from Notes n, Cards c Where c.nid = n.id and c.did = ?", did)
        return maxes[0], maxes[1]
