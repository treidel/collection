from twistar.dbobject import DBObject

class Record(DBObject):
	HASMANY = ['measurements']

class Measurement(DBObject):
	BELONGSTO = ['record']
