"""

This Class is responsible for storage related things

"""
from database.database import Database
from models.clickabletype import ClickableType




class PersistentsManager(object):
    
    def __init__(self, crawl_config):
        self._crawl_config = crawl_config
        self._database = Database(self._crawl_config.name)
        self._web_page_cache = []
        self._deltapage_cache = []
        self._current_crawl_session = None
        self.MAX_CACHE_SIZE = 0 
        
    
    def init_new_crawl_session_for_user(self, crawl_user):
        current_user = self._database.get_user_to_username(crawl_user.username)
        if current_user is not None:
            self.user = current_user
            last_session = current_user.sessions[-1]
            self._current_crawl_session = last_session + 1
            crawl_user.sessions.append(self._current_crawl_session)
            self._database.add_user_session(crawl_user["_id"], self._current_crawl_session)
        else: 
            crawl_user.sessions = [0]
            crawl_user.user_id = self._database.insert_user_and_return_its_id(crawl_user)
            self._current_crawl_session = 0
        return crawl_user
    
    def store_web_page(self, web_page):
        if self.MAX_CACHE_SIZE > 0:
            if len(self._web_page_cache) + 1 > self.MAX_CACHE_SIZE:
                del self._web_page_cache[-1]
            self._web_page_cache.insert(0, web_page)
        self._database.insert_page(self._current_crawl_session, web_page)
    
    def get_page(self, page_id):
        page = self.get_web_page(page_id)
        if page is not None:
            return page
        page = self.get_delta_page(page_id)
        if page is not None:
            return page
        return None
    
    def store_delta_page(self, delta_page):
        if self.MAX_CACHE_SIZE > 0:
            if len(self._deltapage_cache) +1 > self.MAX_CACHE_SIZE:
                del self._deltapage_cache[-1]
            self._deltapage_cache.insert(0, delta_page)
        self._database.insert_delta_page(self._current_crawl_session,delta_page)
    
    def get_web_page(self, page_id):
        for page in self._web_page_cache:
            if page_id == page.id:
                return page
        
        return self._database.get_web_page(page_id, self._current_crawl_session)
            
    
    def get_delta_page(self, delta_page_id):
        for page in self._deltapage_cache:
            if delta_page_id == page.id:
                return page
            
        return self._database.get_delta_page(delta_page_id, self._current_crawl_session)
    
    
    def get_next_url_for_crawling(self):
        return self._database.get_next_url_for_crawling(self._current_crawl_session)
    
    def insert_url(self, url):
        self._database.insert_url(self._current_crawl_session, url)
    
    def visit_url(self, url, webpage_id, response_code):
        self._database.visit_url(self._current_crawl_session, url, webpage_id, response_code)
    
    def extend_ajax_requests_to_webpage(self, webpage, ajax_reuqests):
        self._database.extend_ajax_requests_to_webpage(self._current_crawl_session, webpage, ajax_reuqests)
    
    
    def get_all_crawled_delta_pages(self, url=None):
        return self._database.get_all_crawled_deltapages_to_url(self._current_crawl_session, url)
    
    
    def update_clickable(self, web_page_id, clickable):
        if clickable.clickable_type == ClickableType.Ignored_by_Crawler or clickable.clickable_type == ClickableType.Unsuported_Event:
            self._database.set_clickable_ignored(self._current_crawl_session, web_page_id, clickable.dom_adress, clickable.event, clickable.clickable_depth, clickable.clickable_type)
        else:
            self._database.set_clickable_clicked(self._current_crawl_session, web_page_id, clickable.dom_adress, clickable.event, clickable.clickable_depth, clickable.clickable_type, clickable.links_to)