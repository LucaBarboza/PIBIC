import { initializeApp, getApps, getApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: "AIzaSyARGg3sKYfHYhOCdAgDWHi3n8GfeC3RRak",
  authDomain: "plataforma-aulas.firebaseapp.com",
  projectId: "plataforma-aulas",
  storageBucket: "plataforma-aulas.firebasestorage.app",
  messagingSenderId: "2214721285",
  appId: "1:2214721285:web:20960c3c7f1ba602c8a96c"
};

// Initialize Firebase (Singleton pattern para Next.js)
const app = !getApps().length ? initializeApp(firebaseConfig) : getApp();
const auth = getAuth(app);
const db = getFirestore(app);

export { app, auth, db };
