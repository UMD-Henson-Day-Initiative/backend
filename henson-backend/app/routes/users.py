from flask import Blueprint, request, jsonify
from app.database import supabase

users_bp = Blueprint("users", __name__)

@users_bp.route("/health", methods=['GET'])
def health():
    return jsonify({'health': 'good'}), 400

@users_bp.route("/<user_id>", methods=['GET'])
def getuser(user_id):
    result = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
    if not result.data:
        return jsonify({'error': 'user not found'}), 404
    data = result.data[0]
    return jsonify(data), 200

@users_bp.route("/insertbadge", methods=['POST'])
def insertbadge():
    in_data = request.get_json() or {}
    if not in_data:
        return jsonify({'error': 'nothing in'}), 403
    uid = in_data.get("user_id")
    bid = in_data.get("badge_id")
    response = supabase.table('user_badges').select('user_id', 'badge_id').eq('user_id', uid).eq('badge_id', bid).execute()
    if len(response.data) > 0:
        return jsonify({'error': 'already exists'}), 403
    enter = supabase.table('user_badges').upsert({
        'user_id': uid,
        'badge_id': bid
    }).execute()
    
    ### logic for increasing points can also be here ### !!!
    
    if not enter.data:
        return jsonify({'error': 'something bad happened'}), 500
    return jsonify({'response': 'item was entered into the database'}), 200
    
@users_bp.route("/registeruser", methods=['POST'])
def registeruser():
    # might be updated in the future
    
    
    in_data = request.get_json() or {}
    if not in_data:
        return jsonify({'error': 'nothing in'}), 403
    uname = in_data.get("username")
    avurl = in_data.get("avatar_url")
    response = supabase.table('profiles').upsert({
        'username': uname,
        'avatar_url': avurl,
        'total_points': 0,
        'events_attended': 0
    }).execute()
    if not response.data:
        return jsonify({'error': 'something bad happened'}), 500
    return jsonify({'response': 'new user registered'}), 200

@users_bp.route("/<user_id>", methods=['PATCH'])
def updateuser(user_id):
    in_data = request.get_json() or {}
    if not in_data:
        return jsonify({'error': 'nothing in'}), 403
    check = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
    if not check.data:
        return jsonify({'error': 'user not found'}), 404
    updated_fields = {}
    if in_data.get("username"):
         updated_fields['username'] = in_data.get("username")
    if in_data.get("avatar_url"):
        updated_fields['avatar_url'] = in_data.get("avatar_url")
    if in_data.get("total_points"):
        updated_fields['total_points']= in_data.get("total_points")
    if in_data.get("events_attended"):
        updated_fields['events_attended']= in_data.get("events_attended")
    response = supabase.table('profiles').update(updated_fields).eq("user_id", user_id).execute()
    if not response.data:
        return jsonify({'error': "couldn't insert"}), 500
    return jsonify({'response': 'user updated'}), 200

@users_bp.route("/<user_id>", methods=['DELETE'])
def deleteuser(user_id):
    result = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
    if not result.data:
        return jsonify({'error': 'user not found'}), 404
    deletion = supabase.table("profiles").delete().eq("user_id", user_id).execute()
    if not deletion.data:
        return jsonify({'error': "couldn't delete"}), 500
    return jsonify({'response': 'user deleted successfully'}), 200