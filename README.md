# Inventory Optimization Project

This project contains two main components to manage and optimize inventory data:
- **Frontend**: A Node.js and React-based web application (using Vite + Tailwind).
- **Backend-RL**: A Python FastAPI server providing reinforcement learning routing and backend functionality.

---

## Running the Frontend

The Frontend component provides a user interface to interact with demand settings and view statistics.

1. **Navigate to the Frontend directory:**
   ```bash
   cd Frontend
   ```

2. **Install the dependencies:**
   Make sure you have Node.js installed, then run:
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```

The frontend should now be running locally. Check the terminal output for the exact URL (typically `http://localhost:5000`).

---

## Running the Backend RL

The Backend is built with Python and FastAPI, handling inventory optimization routines and data access.

1. **Navigate to the Backend directory:**
   ```bash
   cd Backend-RL
   ```

2. **Create a virtual environment:**
   It's recommended to use a virtual environment to manage dependencies:
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - On **Windows**:
     ```bash
     venv\Scripts\activate
     ```
   - On **macOS / Linux**:
     ```bash
     source venv/bin/activate
     ```

4. **Install the required packages:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Start the FastAPI server:**
   Navigate into the `src` directory where the main application resides, and run it using `uvicorn`:
   ```bash
   cd src
   uvicorn app:app --reload --port 8000
   ```

The backend server will run at `http://localhost:8000`. 
You can view the Interactive API Documentation (Swagger UI) at `http://localhost:8000/docs`.

---

## Note
Ensure both the frontend and backend servers are running simultaneously for full application functionality.
