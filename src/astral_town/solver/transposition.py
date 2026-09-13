class TranspositionTable:
    def __init__(self):
        self.values={}
        self.hits=0

    def get(self,key):
        if key in self.values:
            self.hits+=1
            return self.values[key]
        return None

    def put(self,key,value):self.values[key]=value
