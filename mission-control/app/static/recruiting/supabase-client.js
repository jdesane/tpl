// TPL Recruiting CRM — Supabase Client
// Loaded after the Supabase CDN script in index.html

const SUPABASE_URL = 'https://zyonidiybzrgklrmalbt.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp5b25pZGl5YnpyZ2tscm1hbGJ0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI3MTY5NzUsImV4cCI6MjA4ODI5Mjk3NX0.5See-qjLkXA4CoJi9tNfcLAX_cdvZhPaxw8iViKM8S8';

const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
