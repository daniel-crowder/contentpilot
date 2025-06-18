"""
Team management views for the web application.
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from ...database.setup import get_session, close_session
from ...database.models import Team, User, Content

# Create blueprint
teams_bp = Blueprint('teams', __name__, url_prefix='/teams')


@teams_bp.route('/')
@login_required
def index():
    """
    Teams list page.
    """
    session = get_session()

    try:
        # Get teams
        teams = session.query(Team).all()

        return render_template('teams/index.html', teams=teams)

    finally:
        close_session(session)


@teams_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """
    Create team page.
    """
    session = get_session()

    try:
        # Get users for member selection
        users = session.query(User).all()

        # Handle form submission
        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description')
            member_ids = request.form.getlist('members')

            # Validate form data
            if not name:
                flash('Team name is required', 'error')
                return render_template('teams/create.html', users=users)

            # Create new team
            try:
                new_team = Team(
                    name=name,
                    description=description
                )

                session.add(new_team)
                session.flush()  # Get the team ID

                # Add members
                if member_ids:
                    members = session.query(User).filter(User.id.in_(member_ids)).all()
                    new_team.members.extend(members)

                # Add current user as a member if not already added
                current_user_obj = session.query(User).filter(User.id == current_user.id).first()
                if current_user_obj and current_user_obj not in new_team.members:
                    new_team.members.append(current_user_obj)

                session.commit()

                flash('Team created successfully', 'success')
                return redirect(url_for('teams.index'))

            except Exception as e:
                session.rollback()
                flash(f'Error creating team: {str(e)}', 'error')

        return render_template('teams/create.html', users=users)

    finally:
        close_session(session)


@teams_bp.route('/edit/<int:team_id>', methods=['GET', 'POST'])
@login_required
def edit(team_id):
    """
    Edit team page.
    """
    session = get_session()

    try:
        # Get team
        team = session.query(Team).filter(Team.id == team_id).first()

        if not team:
            flash('Team not found', 'error')
            return redirect(url_for('teams.index'))

        # Get users for member selection
        users = session.query(User).all()

        # Handle form submission
        if request.method == 'POST':
            team.name = request.form.get('name')
            team.description = request.form.get('description')
            member_ids = request.form.getlist('members')

            # Validate form data
            if not team.name:
                flash('Team name is required', 'error')
                return render_template('teams/edit.html', team=team, users=users)

            try:
                # Update members
                if member_ids:
                    members = session.query(User).filter(User.id.in_(member_ids)).all()
                    team.members = members
                else:
                    team.members = []

                # Add current user as a member if not already added
                current_user_obj = session.query(User).filter(User.id == current_user.id).first()
                if current_user_obj and current_user_obj not in team.members:
                    team.members.append(current_user_obj)

                session.commit()
                flash('Team updated successfully', 'success')
                return redirect(url_for('teams.index'))

            except Exception as e:
                session.rollback()
                flash(f'Error updating team: {str(e)}', 'error')

        return render_template('teams/edit.html', team=team, users=users)

    finally:
        close_session(session)


@teams_bp.route('/delete/<int:team_id>', methods=['POST'])
@login_required
def delete(team_id):
    """
    Delete team.
    """
    session = get_session()

    try:
        # Get team
        team = session.query(Team).filter(Team.id == team_id).first()

        if not team:
            flash('Team not found', 'error')
            return redirect(url_for('teams.index'))

        # Delete team
        session.delete(team)
        session.commit()

        flash('Team deleted successfully', 'success')
        return redirect(url_for('teams.index'))

    except Exception as e:
        session.rollback()
        flash(f'Error deleting team: {str(e)}', 'error')
        return redirect(url_for('teams.index'))

    finally:
        close_session(session)


@teams_bp.route('/view/<int:team_id>')
@login_required
def view(team_id):
    """
    View team details.
    """
    session = get_session()

    try:
        # Get team
        team = session.query(Team).filter(Team.id == team_id).first()

        if not team:
            flash('Team not found', 'error')
            return redirect(url_for('teams.index'))

        # Get team content
        contents = session.query(Content).filter(Content.team_id == team_id).all()

        return render_template('teams/view.html', team=team, contents=contents)

    finally:
        close_session(session)
