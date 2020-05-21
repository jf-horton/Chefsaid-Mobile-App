from functools import partial
import sqlite3

from kivy.core.window import Window
import kivy
from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.floatlayout import FloatLayout
from kivy.properties import ObjectProperty
from kivy.uix.screenmanager import ScreenManager, Screen

# Mobile screen size
Window.size = (335, 640)
kivy.require("1.11.0")

conn = sqlite3.connect('database.db')
curs = conn.cursor()


class DBTable:
    def __init__(self):
        self.ingredients = {}
        self.instructions = []


# Represents the transition between screens
class WindowManager(ScreenManager):
    pass


class Kitchen(Screen):
    item = ObjectProperty(None)
    quantity = ObjectProperty(None)
    food_panel = ObjectProperty(None)
    stock = {}
    # *** new_stock will have only one key value pair at all times
    # so we can update the database correctly
    new_stock = {}
    curs.execute('CREATE TABLE IF NOT EXISTS stock(item TEXT, quantity REAL, step TEXT)')

    def load_screen(self):
        self.download()
        self.fill_food_panel()

    # download database to stock dictionary
    def download(self):
        data = curs.execute("""SELECT * FROM stock""")
        self.table_data = data.fetchall()

        if len(self.table_data) > 0:
            for row in self.table_data:
                self.stock.update({f"{row[0]}": row[1]})

    # upload stock dictionary to database: update or insert into db table as needed
    def upload(self):
        data = curs.execute("""SELECT * FROM stock""")
        self.table_data = data.fetchall()

        if len(self.new_stock) > 0:
            for food in self.new_stock:
                item_exists = False
                for row in self.table_data:
                    if food == row[0]:
                        item_exists = True
                        curs.execute("""UPDATE {tbl} SET quantity = ? WHERE item = ?""".format(tbl='stock'),
                                     (row[1] + self.new_stock[food], food))
                        conn.commit()
                        break
                print(f'{food} exists: {item_exists}')
                if not item_exists:
                    curs.execute("""INSERT INTO {tbl} (item, quantity) VALUES (?, ?)""".format(tbl='stock'),
                                 (food, self.new_stock[food]))
                    conn.commit()
        # ***
        self.new_stock.clear()

    def fill_food_panel(self):
        self.food_panel.clear_widgets()
        for item in self.stock:
            self.food_panel.add_widget(Label(text=item, size_hint=(.3, None)))
            self.food_panel.add_widget(Label(text=str(self.stock[item]),
                                             size_hint=(.3, None)))

    def add_item_and_refresh(self):
        if self.item.text == '' or self.item.text.isdigit():
            message = 'Type a valid food item'
            self.popup_invalid(message)
            return

        try:
            int(self.quantity.text)
        except:
            message = 'Type a valid quantity'
            self.popup_invalid(message)
            return

        self.add_item()
        self.fill_food_panel()
        self.upload()

    def add_item(self):
        if self.item.text in self.stock:
            self.stock[self.item.text] += int(self.quantity.text)
        else:
            self.stock.update({f"{self.item.text}": int(self.quantity.text)})

        # ***
        self.new_stock.update({f"{self.item.text}": int(self.quantity.text)})

        self.item.text = ""
        self.quantity.text = ""
        print(self.stock)

    def popup_invalid(self, message):
        layout = FloatLayout()
        alert = Label(text=message, size_hint=(.6, .2), pos_hint={"x": .2, "top": 1})
        layout.add_widget(alert)

        popup_window = Popup(title='Invalid Input', content=layout,
                             size_hint=(None, None), size=(300, 150))
        popup_window.open()


class Cookbook(Screen):
    recipe_panel = ObjectProperty(None)
    recipe_names = []
    stock = {}

    missing_ingredients = {}

    # download database to dictionary
    def download_db(self, table):
        data = curs.execute("""SELECT * FROM {tbl}""".format(tbl=table))
        table_data = data.fetchall()

        downloaded_db = DBTable()

        if len(table_data) > 0:
            for row in table_data:
                if row[0] is not None:
                    downloaded_db.ingredients.update({f"{row[0]}": row[1]})
                if row[2] is not None:
                    downloaded_db.instructions.append(row[2])
        return downloaded_db

    # update stock database after using a recipe
    def update_db(self, dictionary, table):
        for item in dictionary:
            curs.execute("""UPDATE {tbl} SET quantity = ? WHERE item = ?""".format(tbl=table),
                         (dictionary[item], item))
            conn.commit()
        print(dictionary)

    def get_recipes(self):
        table_names = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        self.recipe_names = []
        for name in table_names:
            if name[0] != 'stock':
                self.recipe_names.append(name[0])

    def fill_recipe_panel(self):
        self.recipe_panel.clear_widgets()
        for recipe in self.recipe_names:
            available = self.are_ingredients_in_stock(recipe)
            if available:
                print("Available!")
                self.recipe_panel.add_widget(Button(text=recipe, size_hint=(.3, None),
                                                    on_press=partial(self.popup_use, recipe)))
            else:
                print("Not available")
                self.recipe_panel.add_widget(Button(text=recipe, size_hint=(.3, None), disabled=True,
                                                    on_press=partial(self.popup_use, recipe)))

            self.recipe_panel.add_widget(Button(text='View', size_hint=(.15, None),
                                                on_press=partial(self.view_recipe, recipe)))

            self.recipe_panel.add_widget(Button(text='Missing\nIngredients', size_hint=(.25, None),
                                                on_press=partial(self.view_missing_ingredients, recipe)))

            self.recipe_panel.add_widget(Button(text='Edit', size_hint=(.15, None),
                                                on_press=partial(self.edit_recipe, recipe)))

            self.recipe_panel.add_widget(Button(text='X', size_hint=(.15, None),
                                                on_press=partial(self.popup_delete, recipe)))

    # pass recipe info to app class
    def edit_recipe(self, *args):
        downloaded_db = self.download_db(args[0])
        App.get_running_app().edit_recipe = True

        # Make the recipe data available to the AddRecipe class
        App.get_running_app().recipe_name = args[0]
        App.get_running_app().ingredients = downloaded_db.ingredients
        App.get_running_app().instructions = downloaded_db.instructions

        App.get_running_app().screen_manager.current = "add recipe"

    def view_recipe(self, *args):
        recipe = args[0]
        recipe_table = self.download_db(recipe)
        self.popup_recipe(recipe_table, recipe)

    def update_recipe_list(self):
        self.get_recipes()
        self.fill_recipe_panel()

    def popup_use(self, *args):
        popup_layout = FloatLayout()
        popup_window = Popup(title="Are you sure you want to use this recipe?",
                             content=popup_layout, size_hint=(.8, .3),
                             auto_dismiss=False)
        popup_layout.add_widget(Button(text='Cancel', size_hint=(.25, .25), pos_hint={"x": .2, "y": .4},
                                       on_release=popup_window.dismiss))
        popup_layout.add_widget(Button(text='Use', size_hint=(.25, .25), pos_hint={"x": .5, "y": .4},
                                       on_press=partial(self.use_recipe_and_refresh, args[0]),
                                       on_release=popup_window.dismiss))
        popup_window.open()

    def use_recipe_and_refresh(self, *args):
        recipe = args[0]
        self.use_recipe(recipe)
        self.update_db(self.stock, 'stock')
        self.fill_recipe_panel()

    def popup_recipe(self, recipe_table, recipe_name):
        scroll_layout = ScrollView(size_hint=(1, 1))
        grid = GridLayout(cols=2, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        ingredients = recipe_table.ingredients
        instructions = recipe_table.instructions

        for item in ingredients:
            grid.add_widget(Label(text=item, size_hint_y=None))
            grid.add_widget(Label(text=str(ingredients[item]), size_hint_y=None))

        i = 0
        for step in instructions:
            i += 1
            grid.add_widget(Label(text=f"step {i}: ", size_hint_y=None))
            grid.add_widget(Label(text=step, size_hint_y=None))

        scroll_layout.add_widget(grid)

        popup_window = Popup(title=recipe_name,
                             content=scroll_layout, size_hint=(.9, .55),
                             auto_dismiss=True)
        popup_window.open()

    def view_missing_ingredients(self, *args):
        recipe_name = args[0]
        available = self.are_ingredients_in_stock(recipe_name)
        self.popup_missing_ingredients(recipe_name, available)

    def popup_missing_ingredients(self, recipe_name, available):
        scroll_layout = ScrollView(size_hint=(1, 1))
        grid = GridLayout(cols=2, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        if not available:
            for item in self.missing_ingredients:
                grid.add_widget(Label(text=item, size_hint_y=None))
                grid.add_widget(Label(text=str(self.missing_ingredients[item]), size_hint_y=None))
            scroll_layout.add_widget(grid)
            popup_window = Popup(title=f"In order to make {recipe_name} you need to buy the following ingredients:",
                                 content=scroll_layout, size_hint=(.9, .55),
                                 auto_dismiss=True)
            popup_window.open()
        else:
            layout = FloatLayout()
            alert = Label(text="no ingredients missing...", size_hint=(.6, .2), pos_hint={"x": .2, "top": 1})
            layout.add_widget(alert)
            popup_window = Popup(title=f"You aren't missing any ingredients to make {recipe_name}.",
                                 content=layout, size_hint=(.9, .55),
                                 auto_dismiss=True)
            popup_window.open()

    def are_ingredients_in_stock(self, recipe):
        self.missing_ingredients.clear()
        ingredients = self.download_db(recipe).ingredients
        temp_stock = self.download_db('stock').ingredients
        available = True

        ingredients_list = list(ingredients.keys())

        if 'None' in ingredients_list:
            ingredients_list.remove('None')

        for key in ingredients_list:
            if key not in temp_stock.keys():
                available = False
                self.missing_ingredients.update({f"{key}": ingredients[key]})
            elif ingredients[key] > temp_stock[key]:
                available = False
                self.missing_ingredients.update({f"{key}": ingredients[key] - temp_stock[key]})
        return available

    def use_recipe(self, recipe):
        recipe_table = self.download_db(recipe)
        ingredients = recipe_table.ingredients
        temp_stock = self.download_db('stock').ingredients

        ingredients_list = list(ingredients.keys())

        if 'None' in ingredients_list:
            ingredients_list.remove('None')

        # use dictionary comprehension to cleanly reduce stock amounts by recipe amounts
        self.stock = {f"{key}": temp_stock[key] - ingredients[key] for key in ingredients_list}

        print("Recipe has been used")
        self.popup_recipe(recipe_table, recipe)

    def remove_recipe(self, recipe):
        conn.execute("DROP TABLE {tbl}".format(tbl=recipe))
        conn.commit()

    def remove_recipe_and_refresh(self, *args):
        self.remove_recipe(args[0])
        self.update_recipe_list()

    def popup_delete(self, *args):
        popup_layout = FloatLayout()
        popup_window = Popup(title="Are you sure you want to delete this recipe?",
                             content=popup_layout, size_hint=(.8, .3),
                             auto_dismiss=False)
        popup_layout.add_widget(Button(text='Cancel', size_hint=(.25, .25), pos_hint={"x": .2, "y": .4},
                                       on_release=popup_window.dismiss))
        popup_layout.add_widget(Button(text='Delete', size_hint=(.25, .25), pos_hint={"x": .5, "y": .4},
                                       on_press=partial(self.remove_recipe_and_refresh, args[0]),
                                       on_release=popup_window.dismiss))
        popup_window.open()


class AddRecipe(Screen):
    recipe_title = ObjectProperty(None)
    item = ObjectProperty(None)
    quantity = ObjectProperty(None)
    step = ObjectProperty(None)
    food_panel = ObjectProperty(None)
    instruction_panel = ObjectProperty(None)
    no_errors = False
    overwrite = True
    recipe_names = []
    instructions = []
    ingredients = {}
    new_ingredients = {}

    # load the data from app class into the AddRecipe screen
    def edit_recipe(self):
        self.recipe_title.text = App.get_running_app().recipe_name
        self.ingredients = App.get_running_app().ingredients
        self.new_ingredients = App.get_running_app().ingredients
        temp_instructions = App.get_running_app().instructions

        for step in temp_instructions:
            step = step.replace('\n', ' ')
            print(step)
            self.step.text = step
            self.add_step_and_refresh()
        self.fill_food_panel()
        self.fill_instruction_panel()

    def save_and_clear(self):
        if self.recipe_title.text == '':
            self.no_errors = False
            message = 'Give a recipe title'
            self.popup_invalid(message)
            return

        if len(self.ingredients) < 1:
            self.no_errors = False
            message = 'Add required ingredients'
            self.popup_invalid(message)
            return

        if len(self.instructions) < 1:
            self.no_errors = False
            message = 'Add instructions'
            self.popup_invalid(message)
            return

        self.no_errors = True
        self.overwrite = True

        # if the table already exists, ask the user if the intent is to overwrite
        if not App.get_running_app().edit_recipe:
            self.get_recipes()
            for name in self.recipe_names:
                if self.recipe_title.text == name:
                    self.popup_overwrite(name)
                    self.overwrite = False
                    return

        self.save_recipe()
        self.clear_recipe()
        App.get_running_app().edit_recipe = False

    def get_recipes(self):
        table_names = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        self.recipe_names = []
        for name in table_names:
            if name[0] != 'stock':
                self.recipe_names.append(name[0])

    def save_recipe(self):
        self.get_recipes()
        for name in self.recipe_names:
            if self.recipe_title.text == name:
                self.remove_recipe(self.recipe_title.text)
        curs.execute("""CREATE TABLE IF NOT EXISTS {tbl}(item TEXT, quantity REAL, step TEXT)""".format(tbl=self.recipe_title.text))
        self.upload_new_recipe()

    def overwrite_recipe(self, *args):
        self.save_recipe()
        self.clear_recipe()
        App.get_running_app().screen_manager.current = "cookbook"

    def remove_recipe(self, recipe):
        conn.execute("DROP TABLE {tbl}".format(tbl=recipe))
        conn.commit()

    def popup_overwrite(self, recipe):
        popup_layout = FloatLayout()
        popup_window = Popup(title=f"A recipe for {recipe} already exists. Do you wish to replace it?",
                             content=popup_layout, size_hint=(None, None), size=(300, 150),
                             auto_dismiss=False)
        popup_layout.add_widget(Button(text='No', size_hint=(.3, .4), pos_hint={"x": .2, "y": .4},
                                       on_release=popup_window.dismiss))
        popup_layout.add_widget(Button(text='Yes', size_hint=(.3, .4), pos_hint={"x": .5, "y": .4},
                                       on_press=self.overwrite_recipe,
                                       on_release=popup_window.dismiss))
        popup_window.open()

    # upload the new recipe based on if len(instructions) > len(ingredients)
    def upload_new_recipe(self):
        step_index = 0
        if len(self.instructions) <= len(self.new_ingredients):
            for food in self.new_ingredients:
                if step_index < len(self.instructions):
                    curs.execute("""INSERT INTO {tbl} (item, quantity, step) VALUES (?, ?, ?)""".format(
                                 tbl=self.recipe_title.text),
                                 (food, self.new_ingredients[food], self.instructions[step_index]))
                    conn.commit()
                    step_index += 1
                else:
                    curs.execute("""INSERT INTO {tbl} (item, quantity) VALUES (?, ?)""".format(
                        tbl=self.recipe_title.text),
                        (food, self.new_ingredients[food]))
                    conn.commit()
            # ***
            self.new_ingredients.clear()
            self.instructions.clear()

        if len(self.new_ingredients) < len(self.instructions):
            for food in self.new_ingredients:
                curs.execute("""INSERT INTO {tbl} (item, quantity, step) VALUES (?, ?, ?)""".format(
                    tbl=self.recipe_title.text),
                    (food, self.new_ingredients[food], self.instructions[step_index]))
                conn.commit()
                step_index += 1
            while step_index < len(self.instructions):
                # remember the comma make your parameters a tuple
                curs.execute("""INSERT INTO {tbl} (step) VALUES (?)""".format(tbl=self.recipe_title.text),
                             (self.instructions[step_index],))
                step_index += 1
                conn.commit()
            # ***
            self.new_ingredients.clear()
            self.instructions.clear()

    def add_step_and_refresh(self):
        if self.step.text == '':
            message = 'Enter a step'
            self.popup_invalid(message)
            return

        self.add_step()
        self.fill_instruction_panel()

    def add_item_and_refresh(self):
        if self.item.text == '' or self.item.text.isdigit():
            message = 'Type a valid food item'
            self.popup_invalid(message)
            return

        try:
            int(self.quantity.text)
        except:
            message = 'Type a valid quantity'
            self.popup_invalid(message)
            return

        self.add_item()
        self.fill_food_panel()

    def popup_invalid(self, message):
        layout = FloatLayout()
        alert = Label(text=message, size_hint=(.6, .2), pos_hint={"x": .2, "top": 1})
        layout.add_widget(alert)

        popup_window = Popup(title='Invalid Input', content=layout,
                             size_hint=(None, None), size=(300, 150))
        popup_window.open()

    def remove_item_and_refresh(self, *args):
        self.ingredients.pop(args[0])
        self.fill_food_panel()

    def remove_step_and_refresh(self, *args):
        self.instructions.pop(self.instructions.index(args[0]))
        self.fill_instruction_panel()

    def clear_recipe(self):
        self.instruction_panel.clear_widgets()
        self.food_panel.clear_widgets()
        self.recipe_title.text = ""
        self.item.text = ""
        self.quantity.text = ""
        self.step.text = ""
        self.instructions.clear()
        self.ingredients.clear()

    def fill_instruction_panel(self):
        self.instruction_panel.clear_widgets()
        for step in self.instructions:
            self.instruction_panel.add_widget(Label(text='Step ' + str(self.instructions.index(step)+1) + ': ',
                                                    size_hint=(.1, None)))
            self.instruction_panel.add_widget(Label(text=step, size_hint=(.4, None)))
            self.instruction_panel.add_widget(Button(text='X', size_hint=(.1, None),
                                                     on_press=partial(self.remove_step_and_refresh, step)))

    def fill_food_panel(self):
        self.food_panel.clear_widgets()
        for food_item in self.ingredients:
            self.food_panel.add_widget(Label(text=food_item, size_hint=(.3, None)))
            self.food_panel.add_widget(Label(text=str(self.ingredients[food_item]),
                                             size_hint=(.3, None)))
            self.food_panel.add_widget(Button(text='X', size_hint=(.1, None),
                                              on_press=partial(self.remove_item_and_refresh, food_item)))

    def add_step(self):
        # wrap the instructions so that the text doesn't
        # overrun the boundaries of the text field
        line_length = 5
        string = ''
        list_of_words = self.step.text.split(' ')

        # add '\n' to every fifth word
        for i in range(0, len(list_of_words), line_length):
            string += ' '.join(list_of_words[i:i+line_length]) + '\n'

        print(string)
        self.instructions.append(string)
        self.step.text = ''

    def add_item(self):
        if self.item.text in self.ingredients:
            self.ingredients[self.item.text] += int(self.quantity.text)
        else:
            self.ingredients.update({f"{self.item.text}": int(self.quantity.text)})

        # ***
        self.new_ingredients.update({f"{self.item.text}": int(self.quantity.text)})

        self.item.text = ""
        self.quantity.text = ""
        print(self.ingredients)


class RepeatingPanel(GridLayout):
    pass


class InstructionPanel(GridLayout):
    pass


class Chefsaid(App):
    def build(self):
        self.screen_manager = WindowManager()
        self.edit_recipe = False
        self.recipe_name = ""
        self.ingredients = {}
        self.instructions = []
        return self.screen_manager


if __name__ == "__main__":
    Chefsaid().run()
