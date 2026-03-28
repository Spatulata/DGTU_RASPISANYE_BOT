import logging
import requests
from typing import Dict, Any
from bot.constants import TPI_DGTY_API_URL, DGTY_API_URL, AUTH_PATH, GET_STUDENT_PATH, GET_TEACHER_PATH, get_current_date

logger = logging.getLogger(__name__)


class TimetableAPI:
    TIMEOUT = 10
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'DGTY-Timetable-Bot/1.0'
        })
    
    def _get_university_url(self, university_type: str) -> str:
        if university_type.startswith('T'):
            return TPI_DGTY_API_URL
        elif university_type.startswith('D'):
            return DGTY_API_URL
        return ""
    
    def _make_request(self, method: str, url: str, error_msg: str, **kwargs) -> requests.Response:
        try:
            response = self.session.request(method, url, timeout=self.TIMEOUT, **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(f"{error_msg}: {e}")
            raise
    
    def auth_user(self, university_type: str, username: str, password: str) -> Dict[str, Any]:
        url = self._get_university_url(university_type) + AUTH_PATH
        payload = {"username": username, "password": password}
        response = self._make_request("POST", url, "Ошибка авторизации", json=payload)
        return response.json()
    
    def get_student_group_id(self, university_type: str, access_token: str, student_id: str) -> int:
        url = self._get_university_url(university_type) + GET_STUDENT_PATH
        cookies = {'authToken': access_token}
        params = {'studentID': student_id}
        response = self._make_request("GET", url, "Ошибка получения ID группы", cookies=cookies, params=params)
        data = response.json()
        return data['data']['group']['item2']
    
    def get_teacher_id(self, university_type: str, access_token: str, user_id: str) -> int:
        url = self._get_university_url(university_type) + GET_TEACHER_PATH
        cookies = {'authToken': access_token}
        params = {'userID': user_id}
        response = self._make_request("GET", url, "Ошибка получения ID преподавателя", cookies=cookies, params=params)
        data = response.json()
        return data['data']['teacherID']
    
    def get_timetable(self, storage_value: str) -> Dict[str, Any]:
        if storage_value.endswith('T'):
            param_name = 'idTeacher'
            value = storage_value[:-1]
        else:
            param_name = 'idGroup'
            value = storage_value
        
        if value.startswith('T') or value.startswith('D'):
            value = value[1:]
        
        university_type = storage_value[0] if storage_value else 'D'
        base_url = self._get_university_url(university_type)
        
        url = f"{base_url}/Rasp"
        params = {param_name: value, 'sdate': get_current_date()}
        
        try:
            response = self._make_request("GET", url, "Ошибка получения расписания", params=params)
            return response.json()
        except Exception as e:
            logger.error(f"Ошибка получения расписания: {e}")
            return {'data': {'rasp': []}, 'state': -1, 'msg': str(e)}
