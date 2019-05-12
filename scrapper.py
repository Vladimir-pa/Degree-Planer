import pickle
import sqlite3
from itertools import product

import requests
from bs4 import BeautifulSoup

from course import Course


def preparePackage(SEM, FAC):
    """Preparing package with given semseter and faculty in order to get courses from UG

    Args:
        SEM (INT): semester number (eg. "201802")
        FAC (INT): faculty  number parsed from UG html
    """
    postPackage = {
            'CNM':      '',
            'CNO':      '',
            'PNT':      '',
            'LLN':      '',
            'LFN':      '',
            'RECALL':   'Y',
            'D1':       'on',
            'D2':       'on',
            'D3':       'on',
            'D4':       'on',
            'D5':       'on',
            'D6':       'on',
            'FTM':      '',
            'TTM':      '',
            'SIL':      '',
            'OPTCAT':   'on',
            'OPTSEM':   'on',
            'doSearch': 'Y',
            'Search':   'חפש',
            'FAC':      FAC,
            'SEM':      SEM
    }
    return postPackage


def getCourses(url, postPackage):
    with requests.Session() as session:
        get = session.post(url, data=postPackage)
        soup = BeautifulSoup(get.content, features="html5lib")
        selects = soup.find_all(lambda a: a.has_attr('href'))
        return uniqueAndSortInput(selects, "content")


def getData(url, tag, attrs, types):
    # //TODO : Get old one working aswell
    with requests.Session() as session:
        get = session.post(url)
        soup = BeautifulSoup(get.content, features="html5lib")
        selects = soup.find_all(tag, attrs)
        return uniqueAndSortInput(selects, types)


def uniqueAndSortInput(selects, part):
    sem = set()
    for a in selects:
        if part == "values":
            if a.attrs != {}:
                for val in a.attrs.values():
                    try:
                        int(val)
                    except ValueError:
                        continue
                    sem.add(int(val))
        if part == "content":
            try:
                int(a.contents[0])
                sem.add(a.contents[0])
            except IndexError:
                continue
            except TypeError:
                continue
            except ValueError:
                continue
        if part == "course":
            return selects  
    return sorted(sem)


def cutDependencies(dependencies):
    result = list()
    dependencies = list(map(str.strip, dependencies.split('|')))
    braces_remove = str.maketrans({"(": None, ")": None})
    for dependence in dependencies:
        temp = list()
        temp.extend(
                map(lambda x: x.translate(braces_remove),
                    map(str.strip, dependence.split('&'))))
        result.append(temp)
    return result


def getCourseInfo(course_number, semester):
    url = "https://ug3.technion.ac.il/rishum/course/" + \
          str(course_number) + "/" + str(semester)
    tag = "div"
    attrs = {"class": "property"}
    types = "course"
    properties = getData(url, tag, attrs, types)
    strip = str.maketrans({"\n": None, "\r": None, "\t": None, "\xa0": " "})
    white_spaces = str.maketrans({" ": None})
    and_trans = str.maketrans({"ו": None, "-": "&"})
    or_trans = str.maketrans({"א": "|", "-": None})
    temp_course = Course()
    for prop in properties:
        sibling = prop.next_sibling.next_sibling.text.translate(strip)
        if "שם מקצוע" in prop.text:
            temp_course.set_name(sibling)
        if "מספר מקצוע" in prop.text:
            temp_course.set_number(sibling.strip())
        if "נקודות" in prop.text:
            temp_course.set_points(sibling.strip())
        if "מקצועות קדם" in prop.text:
            temp_course.add_dependencies(
                    cutDependencies(
                            sibling.translate(and_trans).translate(or_trans)))
        if "מקצועות צמודים" in prop.text:
            temp_course.add_parallel(sibling.split())
        if ":מקצועות ללא זיכוי נוסף" in prop.text:
            temp_course.add_similarities(sibling.split())
        if "מקצועות ללא זיכוי נוסף (מוכלים)" in prop.text:
            temp_course.add_inclusive(sibling.split())
    return temp_course


def updateDb():
    semester_tag = "input"
    semester_attrs = {"type": "radio", "name": "SEM"}
    faculties_tag = "option"
    faculties_attrs = {}
    search_url = 'https://ug3.technion.ac.il/rishum/search'
    semesters = getData(search_url, semester_tag, semester_attrs, "values")
    faculties = getData(search_url, faculties_tag, faculties_attrs, "values")
    packages = []
    for combination in product(semesters, faculties):
        packages.append(preparePackage(combination[0], combination[1]))
    course_numbers = set()
    for package in packages:
        for course in getCourses(search_url, package):
            course_numbers.add(course)
    for course_number in sorted(course_numbers):
        dbAddCourse(getCourseInfo(course_number,
                                  semesters[len(semesters) - 1]))


def updateDb(value='', progressBarUI='', stopFlag='', standAloneFlag=False):
    if not standAloneFlag:
        progressBarUI.label.setText("אוסף מידע:")
    semester_tag = "input"
    semester_attrs = {"type": "radio", "name": "SEM"}
    faculties_tag = "option"
    faculties_attrs = {}
    search_url = 'https://ug3.technion.ac.il/rishum/search'
    semesters = getData(search_url, semester_tag, semester_attrs, "values")
    faculties = getData(search_url, faculties_tag, faculties_attrs, "values")
    packages = []
    for combination in product(semesters, faculties):
        packages.append(preparePackage(combination[0], combination[1]))
    course_numbers = set()
    if not standAloneFlag:
        progressBarUI.label.setText("(1/2) אוסף מספרי קורסים")
    for package in packages:
        for course in getCourses(search_url, package):
            if not standAloneFlag:
                progressBarUI.progressBar.setValue((len(course_numbers) / 600) % 6)
            course_numbers.add(course)
            if not standAloneFlag and stopFlag[0]:
                return
    cnt = 0
    if not standAloneFlag:
        progressBarUI.label.setText("(2/2) מעדכן קורסים")
    for course_number in sorted(course_numbers):
        if not standAloneFlag and stopFlag[0]:
            return
        cnt += 1
        if not standAloneFlag:
            value[0] = 5 + (cnt / len(course_numbers)) * 95
            progressBarUI.progressBar.setValue(value[0])
        dbAddCourse(getCourseInfo(course_number, semesters[len(semesters) - 1]))


def initDB():
    db = sqlite3.connect('./db/courses.db')
    curs = db.cursor()
    curs.execute('CREATE TABLE IF NOT EXISTS courses(course_name STR,'
                 'course_number TEXT PRIMARY KEY,'
                 'points REAL,'
                 'dependencies BIT,'
                 'parallel BIT,'
                 'similarities BIT,'
                 'inclusive BIT)')
    curs.close()
    db.close()


def dbAddCourse(course):
    db = sqlite3.connect('./db/courses.db')
    curs = db.cursor()
    curs.execute('REPLACE INTO courses VALUES(?, ?, ?, ?, ?, ?, ?)',
                 course.to_list())
    db.commit()
    curs.close()
    db.close()


def convertDbEnryToCourse(touple):
    temp_course = Course()
    temp_course.set_name(touple[0])
    temp_course.set_number(touple[1])
    temp_course.set_points(touple[2])
    temp_course.add_dependencies(pickle.loads(touple[3]))
    temp_course.add_parallel(pickle.loads(touple[4]))
    temp_course.add_similarities(pickle.loads(touple[5]))
    temp_course.add_inclusive(pickle.loads(touple[6]))
    return temp_course


def findCourseInDB(course_number):
    db = sqlite3.connect('./db/courses.db')
    curs = db.cursor()
    course_number_tup = (course_number,)
    course = curs.execute('SELECT * FROM courses WHERE  course_number=?',
                          course_number_tup)
    result = course.fetchone()
    if not result:
        curs.close()
        db.close()
        return "הקורס לא נמצא במערכת, נסה שנית."
    else:
        curs.close()
        db.close()
        return convertDbEnryToCourse(result)


def dbToCoursesList():
    db = sqlite3.connect('./db/courses.db')
    curs = db.cursor()
    courses = curs.execute('SELECT * FROM courses')
    temp = list(map(convertDbEnryToCourse, courses))
    curs.close()
    db.close()
    return temp


# combobox.completer().setCompletionMode(QtGui.QCompleter.PopupCompletion)
def loadCourseNameNumberPairs():
    db = sqlite3.connect('./db/courses.db')
    curs = db.cursor()
    courses = curs.execute('SELECT * FROM courses ORDER BY course_number')
    dropdown = list()
    for course in courses:
        dropdown.append(str(course[1]) + " - " + course[0])
    curs.close()
    db.close()
    return dropdown


if __name__ == "__main__":
    initDB()
    updateDb(standAloneFlag=True)
    # a = loadCourseNameNumberPairs()
    # for b in a:
    # print(b)
