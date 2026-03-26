# Guide: Adding Your Own App to Build-Northstar (C3)

This guide is for contributors who want to build a **new Django app** that plugs into this project. You can develop your app in your own fork or branch and have it merged later. Follow these steps and use the exact patterns below so your app looks and behaves like the rest of the site.

---

## 1. Get the project running

- Clone the repo and install dependencies (Python, Django).
- From the project root (where `manage.py` lives), run:
  ```bash
  python manage.py runserver
  ```
- Confirm you can log in and see the Dashboard.

---

## 2. Create your app

From the **project root** (same folder as `manage.py`):

```bash
python manage.py startapp MyFeature
```

Replace `MyFeature` with your app name (use PascalCase, no spaces). Example: `Inventory`, `Calendar`, `Tasks`.

---

## 3. Register your app

**File:** `Build/settings.py`

Find the `INSTALLED_APPS` list and add your app **above** the `django.contrib` apps (e.g. right after `'Dashboard',`):

```python
INSTALLED_APPS = [
    'Profile',
    'Dashboard',
    'MyFeature',   # <-- add this line (use your app name)
    'django.contrib.admin',
    # ... rest unchanged
]
```

---

## 4. Create your app’s URL config

**Create file:** `MyFeature/urls.py`

Use this exact structure (replace `MyFeature` and view names with yours):

```python
from django.urls import path
from . import views

app_name = "MyFeature"

urlpatterns = [
    path("", views.home, name="home"),
    # Add more paths as needed, e.g.:
    # path("list/", views.list_items, name="list"),
    # path("detail/<int:pk>/", views.detail, name="detail"),
]
```

**Important:** Keep `app_name = "MyFeature"` so URLs are namespaced (e.g. `MyFeature:home`).

---

## 5. Wire your app into the project URLs

**File:** `Build/urls.py`

Add an `include()` for your app. Choose a URL prefix (e.g. `myfeature/`):

```python
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("Profile.urls")),
    path("home/", include("Dashboard.urls")),
    path("myfeature/", include("MyFeature.urls")),   # <-- add this line
    # ... any other paths
]
```

Your app’s pages will then live under `/myfeature/` (e.g. `/myfeature/`, `/myfeature/list/`).

---

## 6. Write a view (minimal example)

**File:** `MyFeature/views.py`

Every view that renders a page **must** use the same base template (see Step 7). Minimal example:

```python
from django.shortcuts import render


def home(request):
    """Landing page for MyFeature."""
    return render(request, "MyFeature/home.html")
```

For views that need context (data for the template):

```python
def home(request):
    context = {
        "message": "Hello from MyFeature",
        # add any data your template needs
    }
    return render(request, "MyFeature/home.html", context)
```

---

## 7. Create templates that extend the site base

**Required:** Every page template must extend the project’s base so the navbar, footer, and styling match.

**Create folder:** `MyFeature/templates/MyFeature/`

**Create file:** `MyFeature/templates/MyFeature/home.html`

Use this exact pattern:

```html
{% extends "Dashboard/base.html" %}
{% block title %}My Feature | {{ block.super }}{% endblock title %}
{% block content %}
<h1 class="mb-3">My Feature</h1>
<p>Your content here. Use Bootstrap classes (e.g. btn btn-primary, container, etc.).</p>
{% endblock content %}
```

**Rules:**

- First line must be: `{% extends "Dashboard/base.html" %}`.
- Override only these blocks: `{% block title %}` and `{% block content %}`.
- Use `{% load static %}` only if you need extra static files; the base already loads Bootstrap and `theme.css`.
- For links to your own views, use the namespace: `{% url 'MyFeature:home' %}`, `{% url 'MyFeature:list' %}`, etc.

**Example with a link and user:**

```html
{% extends "Dashboard/base.html" %}
{% block title %}My Feature | {{ block.super }}{% endblock title %}
{% block content %}
<h1 class="mb-3">My Feature</h1>
{% if user.is_authenticated %}
<p>Hello, {{ user.username }}.</p>
{% endif %}
<a href="{% url 'MyFeature:home' %}" class="btn btn-primary">Home</a>
{% endblock content %}
```

---

## 8. Forms and CSRF

For any form that submits with POST, include the CSRF token and use the same Bootstrap styling as the rest of the site:

```html
<form method="post" action="{% url 'MyFeature:some_view' %}">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="btn btn-primary">Submit</button>
</form>
```

---

## 9. What you get for free (don’t redo)

- **Login required:** All your app’s URLs are behind the project’s login; users are redirected to login if not authenticated.
- **Global template context:** In every template you have:
  - `user`
  - `profile_avatar_url`
  - `can_see_users`
  - `can_modify_daily_sales`
  You do **not** need to pass these from your views.
- **Styling:** Base template loads Bootstrap and `static/css/theme.css`. Use Bootstrap classes (e.g. `container`, `btn`, `card`, `table`) for consistency.

---

## 10. Adding your app to the navbar (optional)

To show a link to your app in the top navigation, the project maintainer will edit:

**File:** `Dashboard/templates/Dashboard/base.html`

Inside the `<div class="navbar-nav">` block, add a line like:

```html
<a class="nav-link" href="{% url 'MyFeature:home' %}">My Feature</a>
```

(You can suggest this in your merge request; the maintainer can add it.)

---

## 11. Checklist before you submit / merge

- [ ] App is in `INSTALLED_APPS` in `Build/settings.py`.
- [ ] `Build/urls.py` includes your app with `path("myfeature/", include("MyFeature.urls"))` (or your chosen prefix).
- [ ] Your app has `urls.py` with `app_name = "MyFeature"` and named URL patterns.
- [ ] Every page template extends `Dashboard/base.html` and overrides only `title` and `content`.
- [ ] All forms include `{% csrf_token %}`.
- [ ] Links to your views use `{% url 'MyFeature:view_name' %}` (and optional args).
- [ ] You did not change `Profile` or `Dashboard` code unless necessary for integration.

---

## 12. Merge steps (for the project maintainer)

When merging someone’s app:

1. Copy the new app folder (e.g. `MyFeature/`) into the project root.
2. Add `'MyFeature'` to `INSTALLED_APPS` in `Build/settings.py`.
3. Add `path("myfeature/", include("MyFeature.urls"))` to `Build/urls.py`.
4. (Optional) Add a nav link in `Dashboard/templates/Dashboard/base.html` to `{% url 'MyFeature:home' %}`.
5. Run `python manage.py migrate` if the app has models.
6. Run the app and click through the new URLs to confirm.

---

## Quick reference: lines you must use

| Where | What to use |
|-------|------------------|
| Every page template, line 1 | `{% extends "Dashboard/base.html" %}` |
| Every page template, title | `{% block title %}Your Page Title \| {{ block.super }}{% endblock title %}` |
| Every page template, body | `{% block content %} ... {% endblock content %}` |
| Links to your views | `{% url 'MyFeature:home' %}` (replace `MyFeature` and view name) |
| Forms | `{% csrf_token %}` inside the form |
| Your app’s `urls.py` | `app_name = "MyFeature"` |
| Project `urls.py` | `path("myfeature/", include("MyFeature.urls"))` |
| Project `settings.py` | `'MyFeature',` in `INSTALLED_APPS` |

Replace `MyFeature` and `myfeature` with your app name (PascalCase in Python, lowercase in URL prefix).

---

*Designed by Northstar — Support: admin@northstar.com*
