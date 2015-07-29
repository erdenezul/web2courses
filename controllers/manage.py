# -*- coding: utf-8 -*-

##################################################################################
####                                                                          ####
####                              TEACHER PAGES                               ####
####                                                                          ####
##################################################################################

@auth.requires(auth.has_membership('Teacher') or auth.has_membership('Admin'))
def courses():
    courses = db(Course.course_owner == auth.user.id).select()
    return dict(courses=courses)

@auth.requires(auth.has_membership('Teacher') or auth.has_membership('Admin'))
def classes():
    if request.vars.course:
        course_id = int(request.vars.course)
        classes = db(Class.course == course_id).select(orderby=~Class.start_date)
    else:
        classes = db(Class.course.course_owner == auth.user.id).select(
            orderby=Class.course|~Class.start_date
            )
    return dict(classes=classes)

@auth.requires(lambda: is_course_owner(request.args(0, cast=int))  | auth.has_membership("Admin"))
def lessons():
    import itertools

    class_id = request.args(0,cast=int)

    my_class = Class(id=class_id)
    modules = db(Module.class_id == class_id).select()

    all_lessons = {}
    for module in modules:
        for lesson in module.lessons.select():
            videos = lesson.videos.select()
            texts = lesson.texts.select()
            exercises = lesson.exercises.select()
            merged_records = itertools.chain(videos, texts, exercises)
            contents = sorted(merged_records, key=lambda record: record['place'])
            all_lessons["m%d_l%d" % (module.id, lesson.id)] = contents

    return dict(modules=modules,
                all_lessons=all_lessons,
                my_class=my_class)

@auth.requires(auth.has_membership('Teacher') or auth.has_membership('Admin'))
def pick_type():
    form = SQLFORM.factory(
        Field('type', requires=IS_IN_SET({4: T('Video'), 5: T('Text'), 6: T('Question')}))
        )
    if form.process().accepted:
        redirect(URL('new', args=[int(form.vars.type), request.args(0)], vars=request.vars))
    elif form.errors:
        response.flash(T('Form has errors!'))
    return dict(form=form)

##################################################################################
####                                                                          ####
####                   CRUD PAGES FOR COURSES, CLASSES, ETC                   ####
####                                                                          ####
##################################################################################

@auth.requires(auth.has_membership('Teacher') or auth.has_membership('Admin'))
def new():
    tables = [Course, Class, Module, Lesson, Video, Text, Exercise, Announcement]
    table_type = request.args(0,cast=int)

    if table_type == 0:
        Course.course_owner.default == auth.user.id
    elif table_type == 2:
        Module.class_id.default = request.args(1,cast=int)
        Module.place.default = db(Module.class_id == request.args(1,cast=int)).count()
    elif table_type == 3:
        Lesson.lesson_module.default = request.args(1,cast=int)
        Lesson.place.default = db(Lesson.lesson_module == request.args(1,cast=int)).count()
    elif table_type in [4, 5, 6]:
        lesson = Lesson(id=request.args(1, cast=int))
        counter = lesson.videos.count() + lesson.texts.count() + lesson.exercises.count()
        if table_type == 4:
            Video.place.default = counter
            Video.lesson.default = request.args(1,cast=int)
        elif table_type == 5:
            Text.place.default = counter
            Text.lesson.default = request.args(1,cast=int)
        elif table_type == 6:
            Exercise.place.default = counter
            Exercise.lesson.default = request.args(1,cast=int)
    elif table_type == 7:
        Announcement.class_id.default = request.args(1, cast=int)

    form = SQLFORM(tables[table_type]).process(next=request.vars.next)
    return dict(form=form)

@auth.requires(auth.has_membership('Teacher') or auth.has_membership('Admin'))
def edit():
    tables = [Course, Class, Module, Lesson, Video, Text, Exercise, Announcement]
    table_type = request.args(0,cast=int)
    record_id = request.args(1,cast=int)

    form = SQLFORM(tables[table_type], record_id, showid=False).process(next=request.vars.next)
    return dict(form=form)

@auth.requires(auth.has_membership('Teacher') or auth.has_membership('Admin'))
def delete():
    tables = [Course, Class, Module, Lesson, Video, Text, Exercise, Announcement]
    table_type = request.args(0,cast=int)
    record_id = request.args(1,cast=int)
    db(tables[table_type].id==record_id).delete()
    redirect(request.vars.next)

##################################################################################
####                                                                          ####
####                   CERTIFICATE GENERATION FUNCTIONS                       ####
####                                                                          ####
##################################################################################

@auth.requires(lambda: is_course_owner(request.args(0, cast=int))  | auth.has_membership("Admin"))
def generate_certificate():
    import os.path
    import textwrap
    from PIL import Image

    my_class = Class(id=request.args(0, cast=int))

    upload_folder=os.path.join(request.folder,'uploads/')
    class_folder=os.path.join(upload_folder, 'class%s/' % my_class.id)

    if not os.path.exists(class_folder):
        os.makedirs(class_folder)

    form = SQLFORM(Certificate)
    if form.process().accepted:
        template = Image.open(upload_folder+form.vars.bg_template)
        template = template.resize((3508,2480))
        bg_w, bg_h = template.size
        template_offset = (0, 700)

        signature = Image.open(upload_folder+form.vars.teacher_signature)
        signature = signature.resize((800, 130))
        sig_w, sig_h = signature.size
        signature_offset = (500, 500)
        signature_offset = (bg_w-sig_w-signature_offset[0], bg_h-sig_h-signature_offset[1])

        template.paste(signature, signature_offset, signature)

        template.save(class_folder+"certificate-%s-%s.pdf"%(my_class.course.id, my_class.id), "PDF", resolution=100.0)
        template.save(class_folder+"certificate-%s-%s.jpeg"%(my_class.course.id, my_class.id), "JPEG", resolution=100.0)

    return dict(form=form)

@auth.requires(lambda: is_course_owner(request.args(0, cast=int))  | auth.has_membership("Admin"))
def send_certificate():
    import os.path
    from PIL import Image, ImageFont, ImageDraw

    my_class = Class(id=request.args(0, cast=int))
    students = my_class.students.select()

    upload_folder=os.path.join(request.folder,'uploads/')
    static_folder=os.path.join(request.folder,'static/')
    class_folder=os.path.join(upload_folder, 'class%s/' % my_class.id)

    if not os.path.exists(class_folder+"certificate-%s-%s.jpeg"%(my_class.course.id, my_class.id)):
        session.flash = T("First, import a template and signature!")
        redirect(URL('generate_certificate', args=request.args(0)))

    for student in students:
            certificate = Image.open(class_folder+"certificate-%s-%s.jpeg"%(my_class.course.id, my_class.id))
            draw = ImageDraw.Draw(certificate)
            selectFont = ImageFont.truetype(static_folder+'fonts/Arial Unicode MS.ttf', size=112, encoding="unic")

            bg_w, bg_h = certificate.size
            template_offset = (0, 700)

            lines = []
            lines.append(u"%s" % T("This is to certify that"))
            lines.append(u"%s %s" % (student.student.first_name, student.student.last_name))
            lines.append(u"%s" % T("has satisfactorily completed the course"))
            lines.append(my_class.course.title.decode("utf-8"))
            lines.append(u"%s" % T("from %s to %s" % (my_class.start_date.strftime("%s" % T("%B %d, %Y")), my_class.end_date.strftime("%s" % T("%B %d, %Y")))))
            lines.append(u"%s" % T("in a total of %d hours." % my_class.course.total_hours))

            total_height = 0
            for line in lines:
                line_w, line_h = selectFont.getsize(line)
                line_start_x = ((bg_w-2*template_offset[0])-line_w)/2
                line_start_y = template_offset[1]+total_height+(50*lines.index(line))
                total_height += line_h
                draw.text((line_start_x, line_start_y), line, (0,0,0), font=selectFont)

            certificate.save(class_folder+"certificate-student-%s.pdf"%student.student.id, "PDF", resolution=100.0)

            mail.send(
                to=student.student.email,
                subject=T("%s Certificate" % my_class.course.title),
                message=T("Your Certificate of Conclusion of %s is attached to this email. For more info, contact your teacher.\n\nCongratulations!" \
                         % my_class.course.title),
                attachments=mail.Attachment(class_folder+"certificate-student-%s.pdf"%student.student.id)
                )

    session.flash = T("All certificates sent!")
    redirect(URL('generate_certificate', args=request.args(0, cast=int)))

@auth.requires(lambda: is_course_owner(request.args(0, cast=int))  | auth.has_membership("Admin"))
def preview_certificate():
    import os.path
    from PIL import Image, ImageFont, ImageDraw

    my_class = Class(id=request.args(0, cast=int))

    upload_folder=os.path.join(request.folder,'uploads/')
    static_folder=os.path.join(request.folder,'static/')
    class_folder=os.path.join(upload_folder, 'class%s/' % my_class.id)

    if not os.path.exists(class_folder+"certificate-%s-%s.jpeg"%(my_class.course.id, my_class.id)):
        session.flash = T("First, import a template and signature!")
        redirect(URL('generate_certificate', args=request.args(0)))
    else:
        certificate = Image.open(class_folder+"certificate-%s-%s.jpeg"%(my_class.course.id, my_class.id))
        draw = ImageDraw.Draw(certificate)
        selectFont = ImageFont.truetype(static_folder+'fonts/Arial Unicode MS.ttf', size=112, encoding="unic")

        bg_w, bg_h = certificate.size
        template_offset = (0, 700)

        lines = []
        lines.append(u"%s" % T("This is to certify that"))
        lines.append(u"STUDENT NAME")
        lines.append(u"%s" % T("has satisfactorily completed the course"))
        lines.append(my_class.course.title.decode("utf-8"))
        lines.append(u"%s" % T("from %s to %s" % (my_class.start_date.strftime("%s" % T("%B %d, %Y")), my_class.end_date.strftime("%s" % T("%B %d, %Y")))))
        lines.append(u"%s" % T("in a total of %d hours." % my_class.course.total_hours))

        total_height = 0
        for line in lines:
            line_w, line_h = selectFont.getsize(line)
            line_start_x = ((bg_w-2*template_offset[0])-line_w)/2
            line_start_y = template_offset[1]+total_height+(50*lines.index(line))
            total_height += line_h
            draw.text((line_start_x, line_start_y), line, (0,0,0), font=selectFont)

        certificate.save(class_folder+"preview.pdf", "PDF", resolution=100.0)

    redirect(URL('download_pdf', args=["class%s"%my_class.id, "preview"]))

def download_pdf():
    import os.path
    filepath = request.args
    path=os.path.join(request.folder,'uploads', filepath(0), filepath(1)+".pdf")
    response.headers['ContentType'] ="application/pdf"
    response.headers['Content-Disposition']="inline; %s.pdf"%filepath(1)
    return response.stream(open(path), chunk_size=65536) 