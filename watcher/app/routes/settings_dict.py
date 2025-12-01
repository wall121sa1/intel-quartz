from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.models import db, CustomEntity
from app.services.nlp import NLPService
from app.routes.settings import bp
import csv
import io

@bp.route('/dictionary')
@login_required
def dictionary():
    entities = CustomEntity.query.order_by(CustomEntity.label, CustomEntity.text).all()
    return render_template('settings/dictionary.html', entities=entities)

@bp.route('/dictionary/add', methods=['POST'])
@login_required
def add_custom_entity():
    text = request.form.get('text').strip()
    label = request.form.get('label')
    
    if text and label:
        existing = CustomEntity.query.filter_by(text=text, label=label).first()
        if not existing:
            db.session.add(CustomEntity(text=text, label=label))
            db.session.commit()
            NLPService.reload_model()
            flash(f'Added rule: "{text}" -> {label}')
        else:
            flash('Rule already exists')
            
    return redirect(url_for('settings.dictionary'))

@bp.route('/dictionary/delete/<int:id>')
@login_required
def delete_custom_entity(id):
    entity = CustomEntity.query.get_or_404(id)
    db.session.delete(entity)
    db.session.commit()
    NLPService.reload_model()
    flash('Rule deleted')
    return redirect(url_for('settings.dictionary'))

@bp.route('/dictionary/import', methods=['POST'])
@login_required
def import_dictionary():
    file = request.files.get('file')
    if not file:
        flash('No file uploaded')
        return redirect(url_for('settings.dictionary'))

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        added_count = 0
        for row in csv_input:
            text = row.get('text', '').strip()
            label = row.get('label', '').strip().upper()
            
            if text and label in ['ORG', 'PERSON', 'LOC', 'GPE', 'EVENT', 'TAG', 'TOPIC']:
                exists = CustomEntity.query.filter_by(text=text, label=label).first()
                if not exists:
                    db.session.add(CustomEntity(text=text, label=label))
                    added_count += 1
        
        db.session.commit()
        if added_count > 0:
            NLPService.reload_model()
            
        flash(f'Successfully imported {added_count} new rules.')
        
    except Exception as e:
        flash(f'Error processing CSV: {str(e)}')

    return redirect(url_for('settings.dictionary'))

@bp.route('/dictionary/test', methods=['POST'])
@login_required
def test_dictionary():
    text = request.form.get('test_text')
    if not text:
        flash("Enter text to test.")
        return redirect(url_for('settings.dictionary'))
    
    result = NLPService.process_text(text)
    
    flash(f"Analyzed: '{text}'")
    found_something = False
    for category, items in result['entities'].items():
        if items:
            found_something = True
            flash(f"Found {category.upper()}: {', '.join(items)}")
            
    if not found_something:
        flash("No entities found.")
        
    return redirect(url_for('settings.dictionary'))