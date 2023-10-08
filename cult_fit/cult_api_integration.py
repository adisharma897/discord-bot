import requests
import json
import datetime
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

at = os.environ.get('CULT_FIT_APP_AT')
st = os.environ.get('CULT_FIT_APP_ST')
osname = os.environ.get('CULT_FIT_APP_OSNAME')

commonHeaders = {
    "accept": "application/json",
    "osname": osname
}


cookies = {
    "st": st,
    "at": at
}

CULT_CENTRES = {19: 'Baani, Sector 56',
 145: 'DLF Phase 1',
 188: 'Dwarka Sector 12',
 116: 'Eros Sector 49',
 607: 'Golf Course Rd',
 674: 'Greater Noida West',
 931: 'Gurgaon Sec-56',
 36: 'Hauz Khas',
 91: 'Janakpuri ',
 135: 'Lajpat Nagar (earlier Ring Road)',
 108: 'Model Town',
 107: 'Paschim Vihar',
 864: 'Paschim Vihar - Rohtak Rd',
 92: 'Patel Nagar ',
 101: 'Pitampura',
 136: 'Preet Vihar ',
 52: 'Punjabi Bagh',
 74: 'Rajouri Garden',
 681: 'RDC, Ghaziabad',
 187: 'Saket ',
 286: 'Sector 104 Noida',
 189: 'Sector 18 Noida ',
 121: 'South Extension',
 304: 'Sushant Lok, Phase 1',
 821: 'Universal Trade Tower, Sohna Rd',
 71: 'Vasant Kunj',
 881: 'Vyapar Kendra',
 779: 'Deer Park',
 656: 'Lesiure Valley Park',
 759: 'Noida Stadium',
 657: 'Paschim Vihar District Park',
 658: 'Priya Park',
 761: 'Shivaji Park',
 762: 'Tao Devi Lal Park '}
 

def get_booked_classes(class_data):
    booked_classes = []
    for cult_class in class_data:
        if cult_class['class_booking_code'] != '':
            booked_classes.append(cult_class)
    return booked_classes

def get_selected_class_details(class_data, class_type, class_date, class_timings_bracket):
    priority_classes = []
    for cult_class in class_data:
        if cult_class['class_name'] == class_type \
        and cult_class['class_date'] == class_date \
        and cult_class['class_start_time'] >= class_timings_bracket[0] \
        and cult_class['class_end_time'] <= class_timings_bracket[1]\
        and cult_class['class_booking_code'] == '':
            priority_classes.append(cult_class)
    return priority_classes

def book_class(class_id):
    book_api = f'https://www.cult.fit/api/cult/class/{class_id}/book'
    r = requests.post(book_api, headers=commonHeaders, cookies=cookies, data={})

    json_data = json.loads(r.text)
    if json_data.get('action', '') == 'curefit://orderconfirmation':
        return 'Booking Successful'
    else:
        return json_data.get('title', 'Booking Not Successful')

def cancel_class(booking_code):
    cancel_api = f'https://www.cult.fit/api/cult/booking/{booking_code}/cancel'
    r = requests.post(cancel_api, headers=commonHeaders, cookies=cookies, data={})

    json_data = json.loads(r.text)
    if json_data.get('pageAction', '') == 'Done':
        return 'Cancellation Successful'
    else:
        return 'Cancellation Not Successful'

def get_class_details_v2(center_id=101, date=None):

    class_api = 'https://www.cult.fit/api/cult/classes/v2?productType=FITNESS'
    
    r = requests.get(class_api, headers=commonHeaders, cookies=cookies)
    json_data = json.loads(r.text)
    
    cult_class_data = []
    
    for days in list(json_data.get('classByDateMap', {}).items()):
        if (days[0]==date) or (date is None):
        
            for time in days[1].get('classByTimeList', []):
    
                for center in time.get('centerWiseClasses', []):
                    if center.get('centerId', 0) == center_id:
            
                        for cult_class in center.get('classes', []):
                            class_data = {
                                'class_id': cult_class.get('id', None),
                                'class_date': cult_class.get('date', None),
                                'class_start_time': int(''.join(cult_class.get('startTime', '').split(':')[:2])),
                                'class_end_time': int(''.join(cult_class.get('endTime', '').split(':')[:2])),
                                'center_id': center.get('centerId', None),
                                'class_name': cult_class.get('workoutName', None),
                                'class_available_seats': cult_class.get('availableSeats', None),
                                'class_booking_code': cult_class.get('action', 'bookingNumber=&').split('bookingNumber=')[-1].split('&')[0],
                                'state': cult_class.get('state', None)
                            }
                
                            cult_class_data.append(class_data)


    return cult_class_data

def auto_book_new_classes(center_id=101, day=4):
    new_class_date = (datetime.datetime.today() + datetime.timedelta(days=day)).strftime('%Y-%m-%d')
    cult_class_details = get_class_details_v2(center_id, new_class_date)

    class1 = get_selected_class_details(cult_class_details, 'S&C', new_class_date, [900, 1100])
    class2 = get_selected_class_details(cult_class_details, 'S&C', new_class_date, [1900, 2100])


    if len(class1) > 0:
        logger.info(class1)
        logger.info(book_class(class1[0]['class_id']))
    if len(class2) > 0:
        logger.info(class2)
        logger.info(book_class(class2[0]['class_id']))
        
def lambda_handler(event, context):
    auto_book_new_classes()