import sqlite3
    
class Database(object):
    """ just a bundle of helper functions for convenient database-interaction """

    @staticmethod
    def apply_query(db_path, query, payload=()):
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute(query, payload) #eval
            conn.commit() #apply
            return c

        except sqlite3.Error as e:
            print(e)
            return None


    @staticmethod
    def read(db_path, query, fetch_number=1, result_abstraction=None, payload=()): # retun dict must be ordered dict
        try: 
            c = Database.apply_query(db_path, query, payload=payload) 
            # catch sql-error
            if not c: 
                print("error in read")
                return None

            data = c.fetchmany(fetch_number) # TODO: possible performance implications of fetchmany?
            c.close()

        except sqlite3.Error as e:
            print(e)
            return None
            

        # if we don‘t just want to return a list of tuples, but of objects representing them with a OrderedDict given by result_absctraction
        if result_abstraction and len(data) > 0:
            assert len(data[0]) == len(result_abstraction)
            result = list()
            for data_tuple in data:
                current_result = result_abstraction.copy()
                for i, key in enumerate(current_result):
                    current_result[key] = data_tuple[i]
                result.append(current_result)
            return result

        return data 

