import os
import json
from os.path import join, isdir, isfile
import flask
from flask import render_template, render_template_string, request, redirect, url_for, Response, flash
from flask_user import login_required, UserManager, UserMixin, SQLAlchemyAdapter, current_user
from application import app, db, User, Project, Branch
import string
from shutil import copyfile
import git
from difflib import HtmlDiff

import codecs # deals with encoding better
import sphinx

config_path = 'conf'

def get_git(project, branch):
    repo_path = join('repos', project, branch, 'source')
    repo = git.Repo(repo_path)
    return repo.git

def load_json(path):
    with codecs.open(path, 'r', 'utf-8') as content_file:
        return json.loads(content_file.read())

def write_json(path, structure):
    with codecs.open(path, 'w', 'utf-8') as dest_file:
        dest_file.write(json.dumps(structure))

def get_merging(project, branch):
    merge_file_path = join('repos', project, branch, 'merging.json')
    if isfile(merge_file_path):
        return load_json(merge_file_path)

def std_menu(username):
    return [{'url': '/logout', 'name': 'logout'},
            {'url': '/profile', 'name': username}]

def get_requests(project, branch):
    git_api = get_git(project, branch)
    branches = string.split(git_api.branch())
    merged = string.split(git_api.branch('--merged'))
    unmerged = [item for item in branches if item not in merged]
    bar_menu = std_menu(current_user.username)
    if len(unmerged):
        return render_template('requests.html', project=project, branch=branch,
                               unmerged=unmerged, bar_menu=bar_menu)

def get_pendencies(project, branch):
    # user already has the repository?
    branch_repo_path = join('repos', project, branch)
    if not isdir(branch_repo_path):
        flash('You need to clone this repository first', 'error')
        return redirect('/' + project + '/branches')
    # user is merging?
    merging = get_merging(project, branch)
    if merging:
        return redirect('/' + project + '/' + branch + '/merge/' + merging['branch'])
    # user has a pending request?
    requests = get_requests(project, branch)
    if requests:
        return requests
    # update from reviewer (if the user is not his own reviewer)
    if branch != 'master':
        git_api = get_git(project, branch)
        git_api.fetch()
        git_api.merge('-s', 'recursive', '-Xours', 'origin/master')
        git_api.push('origin', branch)
        build(project, branch)

def config_repo(repo, user_name, email):
    config = repo.config_writer()
    config.set_value('user', 'email', email)
    config.set_value('user', 'name', user_name)

def create_project(project, user_name):
    # create a repository
    repo_path = join('repos', project, 'master')
    os.makedirs(repo_path)
    os.makedirs(join(repo_path, 'source'))
    git.Repo.init(join(repo_path, 'source'))
    repo = git.Repo(join(repo_path, 'source'))
    config_repo(repo, 'master', user_name + '@example.com')
    copyfile('application/empty_repo/source/index.rst', join(repo_path, 'source/index.rst'))
    copyfile('application/empty_repo/.gitignore', join(repo_path, 'source/.gitignore'))
    repo.index.add(['index.rst', '.gitignore'])
    repo.index.commit('Initial commit')
    # add project to database
    user_id = User.query.filter(User.username == user_name).first().id
    new_project = Project(project, user_id)
    db.session.add(new_project)
    # add branch to database
    db.session.commit()
    project_id = Project.query.filter_by(name=project).first().id
    origin_id = 1
    new_branch = Branch('master', project_id, origin_id, user_id)
    db.session.add(new_branch)
    db.session.commit()
    # updating branch self reference
    new_branch = Branch.query.filter_by(project_id=project_id).first()
    new_branch.origin_id = new_branch.id
    db.session.commit()
    # properties = {'project': project, 'owner': user_name, 'reviewer': user_name, 'origin': 'master'}
    # write_json(join('repos', project, 'master', 'properties.json'), properties)
    # properties = {'reviewer': user_name}
    # write_json(join('repos', project, 'master', 'properties.json'), properties)
    build(project, 'master')

def get_branch_owner(project, branch):
    project_id = Project.query.filter_by(name=project).first().id
    return Branch.query.filter_by(project_id=project_id, name=branch).first().owner.username
    # properties = load_json(join('repos', project, branch, 'properties.json'))
    # return properties['owner']

def get_branch_origin(project, branch):
    project_id = Project.query.filter_by(name=project).first().id
    origin_id = Branch.query.filter_by(project_id=project_id, name=branch).first().origin_id
    return Branch.query.filter_by(origin_id=origin_id).first().name
    # properties = load_json(join('repos', project, branch, 'properties.json'))
    # origin = properties['origin']
    # properties = load_json(join('repos', project, origin, 'properties.json'))
    # return properties['reviewer']

def create_branch(project, origin, branch, user_name):
    # Clone repository from a certain origin branch
    repo_path = join('repos', project, branch, 'source')
    main_repo = git.Repo(join('repos', project, origin, 'source'))
    main_repo.clone(os.path.abspath(join(os.getcwd(), repo_path)))
    repo = git.Repo(os.path.abspath(join(os.getcwd(), repo_path)))
    config_repo(repo, user_name, user_name + '@here.com')
    git_api = repo.git
    git_api.checkout('HEAD', b=branch)

    project_id = Project.query.filter_by(name=project).first().id
    origin_id = Branch.query.filter_by(project_id=project_id, name=origin).first().origin_id
    owner_id = User.query.filter_by(username=user_name).first().id
    new_branch = Branch(branch, project_id, origin_id, owner_id)

    db.session.add(new_branch)
    db.session.commit()
    properties = {'origin': origin}
    write_json(join('repos', project, branch, 'properties.json'), properties)
    build(project, branch)

def build(project, branch):
    # Replace this terrible implementation
    config_path = 'conf'
    source_path = join('repos', project, branch, 'source')
    build_path = join('repos', project, branch, 'build/html')
    # args = ['-a', '-c conf']
    # if sphinx.build_main(args + ['source/', 'build/html/']):
    #     os.chdir(previous_wd)
    #     return False
    # os.chdir(previous_wd)
    # return True
    command = 'sphinx-build -c ' + config_path + ' ' + source_path + ' ' + build_path
    os.system(command)
    return True

def build_latex(project, branch):
    # Replace this terrible implementation
    config_path = 'conf'
    source_path = join('repos', project, branch, 'source')
    build_path = join('repos', project, branch, 'build/latex')
    command = 'sphinx-build -a -b latex -c ' + config_path + ' ' + source_path + ' ' + build_path
    os.system(command)
    return True

@login_required
@app.route('/<project>/branches', methods = ['GET', 'POST'])
def branches(project):
    path = join('repos', project)
    branches = [d for d in os.listdir(path) if isdir(join(path, d))]
    bar_menu = std_menu(current_user.username)
    text = {'title': 'Project branches'}
    return render_template('branches.html', project=project, branches=branches,
                           text=text, bar_menu=bar_menu)

@login_required
@app.route('/<project>/<branch>/accept/<path:filename>')
def accept(project, branch, filename):
    if current_user.username != get_branch_owner(project, branch):
        flash('You are not the owner of this branch', 'error')
        return redirect('/' + project + '/' + branch)
    merging = get_merging(project, branch)
    if not merging:
        flash('You are not merging a submission', 'error')
        return redirect('/' + project + '/' + branch)
    if not filename in merging['modified']:
        flash('File ' + filename + ' is not being reviewed', 'error')
        return redirect('/' + project + '/' + branch)
    merging['modified'].remove(filename)
    merging['reviewed'].append(filename)
    merge_file_path = join('repos', project, branch, 'merging.json')
    write_json(merge_file_path, merging)
    return redirect('/' + project + '/' + branch + '/merge/' + merging['branch'])

@login_required
@app.route('/<project>/<branch>/finish')
def finish(project, branch):
    if current_user.username != get_branch_owner(project, branch):
        flash('You are not the owner of this branch', 'error')
        return redirect('/' + project + '/' + branch)
    merging = get_merging(project, branch)
    if not merging:
        flash('You are not merging!', 'error')
        return redirect('/' + project + '/' + branch)
    if len(merging['modified']):
        flash('You still have unreviewed files', 'error')
        return redirect('/' + project + '/' + branch)
    git_api = get_git(project, branch)
    git_api.commit('-m', 'Merge ' + merging['branch'])
    merge_file_path = join('repos', project, branch, 'merging.json')
    os.remove(merge_file_path)
    build(project, branch)
    flash('You have finished merging _' + merging['branch'], 'info')
    return redirect('/' + project + '/' + branch + '/view/index.html')

@app.route('/<project>/<branch>/view/<path:filename>')
def view(project, branch, filename):
    filename, file_extension = os.path.splitext(filename)
    if file_extension == '':
        file_extension = '.html'
    user_repo_path = join('repos', project, branch,
                          'build/html', filename + file_extension)
    if (current_user.is_authenticated):
        pendencies = get_pendencies(project, branch)
        if pendencies:
            return pendencies
        bar_menu = [{'url': '/logout', 'name': 'logout'},
                    {'url': '/' + project + '/' + branch + '/edit/' + filename, 'name': 'edit'},
                    {'url': '/profile', 'name': current_user.username}]
    else:
        bar_menu = [{'url': '/login', 'name': 'login'}]
    build(project, branch)
    with codecs.open(user_repo_path, 'r', 'utf-8') as content_file:
        content = content_file.read()
    return render_template_string(content, bar_menu=bar_menu, render_sidebar=True)

@login_required
@app.route('/<project>/<branch>/save/<path:filename>', methods = ['GET', 'POST'])
def save(project, branch, filename):
    if current_user.username != get_branch_owner(project, branch):
        flash('You are not the owner of this branch', 'error')
        return redirect('/' + project + '/' + branch)
    pendencies = get_pendencies(project, branch)
    if pendencies:
        return pendencies
    filename, file_extension = os.path.splitext(filename)
    user_repo_path = join('repos', project, branch)
    if request.method == 'POST':
        with codecs.open(join(user_repo_path, 'source', filename + '.rst'), 'w') as dest_file:
            dest_file.write(request.form['code'].encode('utf8'))
    repo = git.Repo(join(user_repo_path, 'source'))
    repo.index.add([filename + '.rst'])
    repo.index.commit('Change in ' + filename + ' by ' + current_user.username)
    git_api = repo.git
    origin = get_branch_origin(project, branch)
    if branch != origin:
        git_api.push('origin', branch)
        flash('Page submitted to _' + origin, 'info')
    build(project, branch)
    return redirect('/' + project + '/' + branch + '/view/' + filename)

@login_required
@app.route('/<project>/<branch>/edit/<path:filename>', methods = ['GET', 'POST'])
def edit(project, branch, filename):
    if current_user.username != get_branch_owner(project, branch):
        flash('You are not the owner of this branch', 'error')
        return redirect('/' + project + '/' + branch + '/clone')
    pendencies = get_pendencies(project, branch)
    if pendencies:
        return pendencies
    branch_source_path = join('repos', project, branch, 'source', filename + '.rst')
    branch_html_path = join('repos', project, branch, 'build/html', filename + '.html')
    if request.method == 'POST':
        with codecs.open(branch_source_path, 'w') as dest_file:
            dest_file.write(request.form['code'].encode('utf8'))
    build(project, branch)
    with codecs.open(branch_source_path, 'r', 'utf-8') as content_file:
        rst = content_file.read()
    with codecs.open(branch_html_path, 'r', 'utf-8') as content_file:
        doc = render_template_string(content_file.read(), barebones=True)
    text = {'title': 'Edit:', 'image': 'Image', 'math': 'Math mode',
            'sections': 'Sections', 'style': 'Style',
            'cancel': 'Cancel', 'preview': 'Preview', 'submit': 'Submit'}
    return render_template('edit.html', doc=doc, rst=rst, filename=filename, branch=branch,
                           project=project, text=text, render_sidebar=False)

@login_required
@app.route('/<project>/<branch>/diff/<path:filename>')
def diff(project, branch, filename):
    if current_user.username != get_branch_owner(project, branch):
        flash('You are not the owner of this branch', 'error')
        return redirect('/' + project + '/' + branch)
    merging = get_merging(project, branch)
    if not merging:
        flash('You are not merging', 'error')
        return redirect('/' + project)
    bar_menu = std_menu(current_user.username)
    differ = HtmlDiff()
    filename, file_extension = os.path.splitext(filename)
    branch_source_path = join('repos', project, branch, 'source', filename + '.rst')
    with codecs.open(branch_source_path, 'r', 'utf-8') as content_file:
        new = string.split(content_file.read(), '\n')
    git_api = get_git(project, branch)
    old = string.split(git_api.show('master:' + filename + file_extension), '\n')
    diff = differ.make_table(new, old)
    diff = string.replace(diff, 'nowrap="nowrap"', '')
    text = {'title': ' has suggested a change to the file: ',
            'instructions': 'The proposed version is on the left, while the old version is on the right.'}
    return render_template('diff.html',  project=project, other=merging['branch'],
                           diff=diff, filename=filename + file_extension, branch=branch,
                           text=text, bar_menu=bar_menu)

@login_required
@app.route('/<project>/<branch>/merge/<other>')
def merge(project, branch, other):
    merging = get_merging(project, branch)
    if not merging:
        git_api = get_git(project, branch)
        git_api.merge('--no-commit', '--no-ff', '-s', 'recursive', '-Xtheirs', other)
        modified = string.split(git_api.diff('HEAD', '--name-only'))
        merging = {'branch': other, 'modified': modified, 'reviewed': []}
        write_json(join('repos', project, branch, 'merging.json'), merging)
    bar_menu = std_menu(current_user.username)
    text = {'title': 'Merging from _', 'unseen': 'Modifications not yet reviewed',
            'review': 'Review file', 'accept': 'Accept suggestions', 'view': 'View differences',
            'reviewed': 'Changes reviewed', 'finally': 'You have finished all the reviews',
            'finish': 'Finish merge'}
    return render_template('merge.html', project=project, modified=merging['modified'],
                           reviewed=merging['reviewed'], branch=branch, other=other,
                           text=text, bar_menu=bar_menu)

@app.route('/<project>')
def index(project):
    text = {'title': 'List of branches'}
    if (current_user.is_authenticated):
        bar_menu = std_menu(current_user.username)
    else:
        bar_menu = [{'url': '/login', 'name': 'login'}]
    return render_template('branches.html', text=text, project=project, bar_menu=bar_menu)

@app.route('/')
def projects():
    path = 'repos'
    projects = [d for d in os.listdir(path) if isdir(join(path, d))]
    if current_user.is_authenticated:
        bar_menu = std_menu(current_user.username)
    else:
        bar_menu = [{'url': '/login', 'name': 'login'}]
    text = {'title': 'Projects list', 'download': 'Download', 'new': 'Create new project'}
    return render_template('projects.html', projects=projects, bar_menu=bar_menu,
                           text=text, copyright='CC-BY-SA-NC')

@app.route('/profile')
def profile():
    if not current_user.is_authenticated:
        redirect (url_for('login'))
    bar_menu = std_menu(current_user.username)
    return render_template('profile.html', username=current_user.username, bar_menu=bar_menu)

@app.route('/new', methods = ['GET', 'POST'])
def new():
    if not current_user.is_authenticated:
        flash('You need to be logged in to create a new project', 'error')
        return redirect(url_for('login'))
    bar_menu = std_menu(current_user.username)
    if request.method == 'POST':
        user_repo_path = join('repos', request.form['project'], current_user.username)
        if os.path.isdir(user_repo_path):
            flash('This project name already exists', 'error')
            return render_template('new.html', username=current_user.username, bar_menu=bar_menu)
        else:
            create_project(request.form['project'], current_user.username)
            flash('Project created successfuly!', 'info')
            return redirect('/')
    text = {'title': 'Create new project', 'submit': 'Submit'}
    return render_template('new.html', username=current_user.username,
                           text=text, bar_menu=bar_menu)

@app.route('/<project>/<branch>/clone', methods = ['GET', 'POST'])
def clone(project, branch):
    if not current_user.is_authenticated:
        flash('You need to be logged in to clone a project', 'error')
        return redirect(url_for('login'))
    bar_menu = std_menu(current_user.username)
    if request.method == 'POST':
        new_repo_path = join('repos', project, request.form['name'])
        if os.path.isdir(new_repo_path):
            flash('This branch name already exists', 'error')
            return redirect('/' + project + '/' + branch + '/clone')
        else:
            new_branch = request.form['name']
            create_branch(project, branch, new_branch, current_user.username)
            flash('Project cloned successfuly!', 'info')
            return redirect('/' + project + '/' + new_branch + '/view/index.html')
    path = join('repos', project)
    branches = [d for d in os.listdir(path) if isdir(join(path, d))]
    text = {'title': 'Create your own branch of this project', 'submit': 'Submit',
            'name': 'Choose branch name'}
    return render_template('clone.html', username=current_user.username, project=project,
                           branch=branch, branches=branches, text=text, bar_menu=bar_menu)

@app.route('/<project>/pdf')
def pdf(project):
    if (current_user.is_authenticated):
        build_path = os.path.abspath(join('repos', project, current_user.username, 'build/latex'))
    else:
        build_path = os.path.abspath(join('repos', project, get_creator(project), 'build/latex'))
    build_latex(project, current_user.username)
    command = '(cd ' + build_path + '; pdflatex -interaction nonstopmode linux.tex > /tmp/222 || true)'
    os.system(command)
    return flask.send_from_directory(build_path, 'linux.pdf')

@app.route('/<project>/comment_summary/<path:filename>')
def comment_summary(project, filename):
    return 'Comments from ' + filename

@app.route('/<project>/<action>/_images/<path:filename>')
@app.route('/edit/<project>/images/<path:filename>', methods = ['GET'])
def get_tikz(project, action, filename):
    images_path = join('repos', project, current_user.username, 'build/html/_images')
    return flask.send_from_directory(os.path.abspath(images_path), filename)

@app.route('/<project>/<action>/_static/<path:filename>')
def get_static(project, action, filename):
    if (current_user.is_authenticated):
        user_repo_path = join('repos', project, current_user.username)
    else:
        user_repo_path = join('repos', project, get_creator(project))
    return flask.send_from_directory(os.path.abspath(join(user_repo_path, 'build/html/_static/')), filename)

@app.route('/_static/<path:filename>')
def get_global_static(filename):
    return flask.send_from_directory(os.path.abspath('conf/biz/static/'), filename)

@app.route('/_sources/<path:filename>')
def show_source(filename):
    sources_path = join('repos', current_user.username, 'build/html/_sources', filename)
    with codecs.open(sources_path, 'r', 'utf-8') as content_file:
        content = content_file.read()
    return Response(content, mimetype='text/txt')

@app.route('/<project>/images/<path:filename>')
def get_image(project, filename):
    return flask.send_from_directory(os.path.abspath('repos/' + project + '/images'), filename)

@app.route('/<project>/view/genindex.html')
def genindex(project):
    return redirect('/' + project + '/view/index')

@app.route('/login')
def login():
    return redirect(url_for('user.login'))

@app.route('/logout')
def logout():
    return redirect(url_for('user.logout'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# @app.errorhandler(403)
# def page_forbidden(e):
#     return render_template('403.html'), 500


