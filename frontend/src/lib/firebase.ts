// lib/firebase.ts
import { initializeApp, getApps, FirebaseApp } from "firebase/app";
import { getAuth, Auth, inMemoryPersistence } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

let app: FirebaseApp | undefined;
let auth: Auth | undefined;

// If we have dummy credentials, we're likely in a dev mode without Firebase.
// We'll initialize an empty app and handle auth fallbacks in our api client.
const isDummyConfig = firebaseConfig.apiKey === "dummy_api_key";

if (typeof window !== "undefined") {
  if (!getApps().length && !isDummyConfig && firebaseConfig.apiKey) {
    try {
      app = initializeApp(firebaseConfig);
      auth = getAuth(app);
    } catch (e) {
      console.error("Failed to initialize Firebase", e);
    }
  } else if (isDummyConfig) {
    console.warn("Using dummy Firebase config. Auth will be mocked.");
  }
}

export { app, auth };
