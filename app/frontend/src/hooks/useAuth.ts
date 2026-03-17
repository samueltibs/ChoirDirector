import { useState, useEffect, useCallback } from 'react';
import { User, Session } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import { api } from '../lib/api';

export interface Member {
  id: string;
  email: string;
  full_name: string;
  role: string;
  customer_id: string;
  customer_slug?: string;
  created_at?: string;
  updated_at?: string;
}

export interface AuthState {
  user: User | null;
  member: Member | null;
  session: Session | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  signup: (email: string, password: string, fullName: string, customerSlug: string) => Promise<void>;
}

export function useAuth(): AuthState {
  const [user, setUser] = useState<User | null>(null);
  const [member, setMember] = useState<Member | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchMemberProfile = useCallback(async (accessToken: string): Promise<void> => {
    try {
      const data = await api.get<Member>('/auth/me', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      setMember(data);
    } catch (error) {
      console.error('Failed to fetch member profile:', error);
      setMember(null);
    }
  }, []);

  useEffect(() => {
    let mounted = true;

    const initializeAuth = async () => {
      try {
        const { data: { session: currentSession }, error } = await supabase.auth.getSession();
        if (error) {
          console.error('Error getting session:', error);
        }
        if (mounted) {
          setSession(currentSession);
          setUser(currentSession?.user ?? null);
          if (currentSession?.access_token) {
            await fetchMemberProfile(currentSession.access_token);
          }
        }
      } catch (error) {
        console.error('Error initializing auth:', error);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    initializeAuth();

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, newSession) => {
        if (!mounted) return;

        setSession(newSession);
        setUser(newSession?.user ?? null);

        if (event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED') {
          if (newSession?.access_token) {
            await fetchMemberProfile(newSession.access_token);
          }
        } else if (event === 'SIGNED_OUT') {
          setMember(null);
        }

        setLoading(false);
      }
    );

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, [fetchMemberProfile]);

  const login = useCallback(async (email: string, password: string): Promise<void> => {
    setLoading(true);
    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) {
        throw error;
      }

      if (data.session?.access_token) {
        await fetchMemberProfile(data.session.access_token);
      }
    } catch (error) {
      setLoading(false);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [fetchMemberProfile]);

  const logout = useCallback(async (): Promise<void> => {
    setLoading(true);
    try {
      const { error } = await supabase.auth.signOut();
      if (error) {
        throw error;
      }
      setUser(null);
      setMember(null);
      setSession(null);
    } catch (error) {
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  const signup = useCallback(async (
    email: string,
    password: string,
    fullName: string,
    customerSlug: string
  ): Promise<void> => {
    setLoading(true);
    try {
      const response = await api.post<{ session: Session; member: Member }>('/auth/signup', {
        email,
        password,
        full_name: fullName,
        customer_slug: customerSlug,
      });

      if (response.session) {
        const { error: sessionError } = await supabase.auth.setSession({
          access_token: response.session.access_token,
          refresh_token: response.session.refresh_token,
        });

        if (sessionError) {
          throw sessionError;
        }

        setSession(response.session);
        setUser(response.session.user);
      }

      if (response.member) {
        setMember(response.member);
      } else if (response.session?.access_token) {
        await fetchMemberProfile(response.session.access_token);
      }
    } catch (error) {
      throw error;
    } finally {
      setLoading(false);
    }
  }, [fetchMemberProfile]);

  return {
    user,
    member,
    session,
    loading,
    login,
    logout,
    signup,
  };
}
