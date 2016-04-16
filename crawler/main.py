import logging, sys, json

from attacker import Attacker
from crawler import Crawler
from database.databasemanager import DatabaseManager
from utils.config import CrawlConfig, AttackConfig
from models.utils import CrawlSpeed
from utils.user import User
import csv
from utils.utils import calculate_similarity_between_pages
from afterclickshandlers import LoginPageChecker
from HSTSPreloadList import HSTSPreloadList

# Here you can specify the logging. Now it logs to the console. If you uncomment the two lines below, then it logs in the file.
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s: %(levelname)s - %(message)s',
                    #filename='Attack.log',
                    #filemode='w'
                    )

if __name__ == '__main__':
    if len(sys.argv) == 3:
        url = sys.argv[1]
        domain = sys.argv[2]
    else:
        indata = json.load(open(sys.argv[1]))
        url = indata["url"]
        domain = indata["domain"]

    dbname = domain.replace(".", "_")

    # Crawl without user session. Parameter desc: Name of DB - Privilege level - session
    user = User(dbname, 0, session="ABC")
    crawler_config = CrawlConfig("Some Name, doesn't matter", url, max_depth=3, max_click_depth=3, crawl_speed=CrawlSpeed.Fast)

    # From here you have nothing to chance. Except you want no attacking, then comment out the lines down
    logging.info("Crawler started...")
    database_manager = DatabaseManager(user, dropping=True)
    hstspreloadchecker = HSTSPreloadList()
    xxx = LoginPageChecker("CRAWL", None, hstspreloadchecker, domain = domain, autoExitFilename = "output-jaek.json")
    crawler = Crawler(crawl_config=crawler_config, database_manager=database_manager, afterClicksHandler=xxx)#, proxy="localhost", port=8082)
    crawler.crawl(user)
    logging.info("Crawler finished")

    if xxx.hasResult():
        res = xxx.getResult()
        # these will be bogus when running jAEk because it doesn't reset the arrays on every page
        res["redirectPageResources"] = None
        res["links"] = None
        with open(xxx.autoExitFilename, 'w') as outfile:
            json.dump(res, outfile)
    sys.exit(0)

