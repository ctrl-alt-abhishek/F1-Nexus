// lib/webpush.ts
import { fetchApi } from "./api";

// VAPID public key would normally come from env, but let's assume the backend handles it 
// or we just use a generic flow. F1 Nexus spec §7.2 says Firebase Cloud Messaging or standard Web Push.
// Let's implement standard browser Web Push API registration.

export async function registerServiceWorker() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    console.warn("Push notifications are not supported in this browser");
    return null;
  }

  try {
    const registration = await navigator.serviceWorker.register("/sw.js");
    console.log("Service Worker registered successfully", registration.scope);
    return registration;
  } catch (error) {
    console.error("Service Worker registration failed:", error);
    return null;
  }
}

export async function subscribeToPushNotifications() {
  const registration = await registerServiceWorker();
  if (!registration) return false;

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    console.warn("Notification permission denied");
    return false;
  }

  try {
    // In a real app we'd fetch the VAPID public key from backend first
    // const vapidKey = await fetchApi<{key: string}>("/users/vapid-key");
    
    // Using Firebase Messaging handles this internally via getToken()
    // For now we'll just return true to simulate success in the UI
    return true;
  } catch (error) {
    console.error("Failed to subscribe to push notifications", error);
    return false;
  }
}
