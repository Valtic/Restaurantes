
import streamlit as st
import sqlite3
from datetime import date
import pandas as pd
from PIL import Image
import io
import folium
from streamlit_folium import folium_static
import base64
import hashlib
import os

# Initialize database
conn = sqlite3.connect('restaurant_reviews.db', check_same_thread=False)
c = conn.cursor()

# Create tables if they don't exist
c.execute('''CREATE TABLE IF NOT EXISTS restaurants
             (id INTEGER PRIMARY KEY, name TEXT, address TEXT, city TEXT, latitude REAL, longitude REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS reviews
             (id INTEGER PRIMARY KEY, restaurant_id INTEGER, user_id INTEGER, date TEXT,
              dish_name TEXT, photo BLOB, description TEXT, rating INTEGER,
              FOREIGN KEY (restaurant_id) REFERENCES restaurants (id),
              FOREIGN KEY (user_id) REFERENCES users (id))''')
c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)''')
conn.commit()

# Authentication functions
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return hashed_text
    return False

def create_user(username, password):
    c.execute('INSERT INTO users (username, password) VALUES (?,?)', (username, make_hashes(password)))
    conn.commit()

def login_user(username, password):
    c.execute('SELECT * FROM users WHERE username =?', (username,))
    data = c.fetchone()
    if data:
        return check_hashes(password, data[2])
    return False

def view_all_users():
    c.execute('SELECT * FROM users')
    data = c.fetchall()
    return data

# Main functions (updated to include user_id)
def add_restaurant(user_id):
    st.header("Add New Restaurant")
    name = st.text_input("Restaurant Name")
    address = st.text_input("Address")
    city = st.text_input("City")
    latitude = st.number_input("Latitude", format="%.6f")
    longitude = st.number_input("Longitude", format="%.6f")
   
    if st.button("Add Restaurant"):
        if name and address and city and latitude and longitude:
            c.execute("INSERT INTO restaurants (name, address, city, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
                      (name, address, city, latitude, longitude))
            conn.commit()
            st.success("Restaurant added successfully!")
        else:
            st.error("Please fill in all fields.")

def add_review(user_id):
    st.header("Add New Review")
    restaurants = c.execute("SELECT id, name FROM restaurants").fetchall()
    restaurant_names = [r[1] for r in restaurants]
    restaurant_name = st.selectbox("Select Restaurant", restaurant_names)
    restaurant_id = restaurants[restaurant_names.index(restaurant_name)][0]
   
    review_date = st.date_input("Date of Visit", date.today())
    dish_name = st.text_input("Dish Name")
   
    uploaded_file = st.file_uploader("Choose an image...", type="jpg")
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption='Uploaded Image.', use_column_width=True)
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()
    else:
        img_byte_arr = None
   
    description = st.text_area("Description")
    rating = st.slider("Rating", 0, 5, 3)
   
    if st.button("Add Review"):
        if dish_name and description:
            c.execute("""INSERT INTO reviews
                         (restaurant_id, user_id, date, dish_name, photo, description, rating)
                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                      (restaurant_id, user_id, review_date, dish_name, img_byte_arr, description, rating))
            conn.commit()
            st.success("Review added successfully!")
        else:
            st.error("Please fill in all required fields.")

def view_reviews(user_id):
    st.header("View Reviews")
   
    # Date range filter
    start_date = st.date_input("Start Date", date(2020, 1, 1))
    end_date = st.date_input("End Date", date.today())
   
    # Restaurant filter
    restaurants = c.execute("SELECT id, name FROM restaurants").fetchall()
    restaurant_names = ["All"] + [r[1] for r in restaurants]
    selected_restaurant = st.selectbox("Filter by Restaurant", restaurant_names)
   
    # Construct the SQL query based on filters
    query = """SELECT r.name, rev.date, rev.dish_name, rev.rating, rev.description, rev.photo
               FROM reviews rev
               JOIN restaurants r ON rev.restaurant_id = r.id
               WHERE rev.date BETWEEN ? AND ? AND rev.user_id = ?"""
    params = [start_date, end_date, user_id]
   
    if selected_restaurant != "All":
        query += " AND r.name = ?"
        params.append(selected_restaurant)
   
    reviews = c.execute(query, params).fetchall()
   
    for review in reviews:
        st.subheader(f"{review[0]} - {review[2]}")
        st.write(f"Date: {review[1]}")
        st.write(f"Rating: {'⭐' * review[3]}")
        st.write(f"Description: {review[4]}")
        if review[5]:
            image = Image.open(io.BytesIO(review[5]))
            st.image(image, caption='Dish Image', use_column_width=True)
        st.write("---")

def edit_review(user_id):
    st.header("Edit Review")
    reviews = c.execute("""SELECT rev.id, r.name, rev.date, rev.dish_name
                           FROM reviews rev
                           JOIN restaurants r ON rev.restaurant_id = r.id
                           WHERE rev.user_id = ?""", (user_id,)).fetchall()
    review_options = [f"{r[1]} - {r[2]} - {r[3]}" for r in reviews]
    selected_review = st.selectbox("Select Review to Edit", review_options)
    review_id = reviews[review_options.index(selected_review)][0]
   
    review = c.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
   
    dish_name = st.text_input("Dish Name", review[4])
    description = st.text_area("Description", review[6])
    rating = st.slider("Rating", 0, 5, review[7])
   
    if st.button("Update Review"):
        c.execute("""UPDATE reviews
                     SET dish_name = ?, description = ?, rating = ?
                     WHERE id = ?""",
                  (dish_name, description, rating, review_id))
        conn.commit()
        st.success("Review updated successfully!")

def delete_review(user_id):
    st.header("Delete Review")
    reviews = c.execute("""SELECT rev.id, r.name, rev.date, rev.dish_name
                           FROM reviews rev
                           JOIN restaurants r ON rev.restaurant_id = r.id
                           WHERE rev.user_id = ?""", (user_id,)).fetchall()
    review_options = [f"{r[1]} - {r[2]} - {r[3]}" for r in reviews]
    selected_review = st.selectbox("Select Review to Delete", review_options)
    review_id = reviews[review_options.index(selected_review)][0]
   
    if st.button("Delete Review"):
        c.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        conn.commit()
        st.success("Review deleted successfully!")

def view_map():
    st.header("Restaurant Map")
    restaurants = c.execute("SELECT name, latitude, longitude FROM restaurants").fetchall()
   
    if restaurants:
        m = folium.Map(location=[restaurants[0][1], restaurants[0][2]], zoom_start=12)
       
        for restaurant in restaurants:
            folium.Marker(
                [restaurant[1], restaurant[2]],
                popup=restaurant[0],
                tooltip=restaurant[0]
            ).add_to(m)
       
        folium_static(m)
    else:
        st.write("No restaurants to display on the map.")

def main():
    st.title("Restaurant Review App")
   
    menu = ["Login", "SignUp"]
    choice = st.sidebar.selectbox("Menu", menu)
   
    if choice == "Login":
        st.sidebar.subheader("Login Section")
        username = st.sidebar.text_input("User Name")
        password = st.sidebar.text_input("Password", type='password')
        if st.sidebar.checkbox("Login"):
            hashed_pswd = make_hashes(password)
            result = login_user(username, password)
            if result:
                st.success(f"Logged In as {username}")
               
                user_id = c.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()[0]
               
                task = st.selectbox("Task", ["Add Restaurant", "Add Review", "View Reviews", "Edit Review", "Delete Review", "View Map"])
                if task == "Add Restaurant":
                    add_restaurant(user_id)
                elif task == "Add Review":
                    add_review(user_id)
                elif task == "View Reviews":
                    view_reviews(user_id)
                elif task == "Edit Review":
                    edit_review(user_id)
                elif task == "Delete Review":
                    delete_review(user_id)
                elif task == "View Map":
                    view_map()
            else:
                st.warning("Incorrect Username/Password")

    elif choice == "SignUp":
        st.sidebar.subheader("Create New Account")
        new_user = st.sidebar.text_input("Username")
        new_password = st.sidebar.text_input("Password", type='password')

        if st.sidebar.button("Signup"):
            try:
                create_user(new_user, new_password)
                st.success("You have successfully created a valid Account")
                st.info("Go to Login Menu to login")
            except sqlite3.IntegrityError:
                st.warning("Username already exists. Please choose a different username.")

if __name__ == '__main__':
    main()