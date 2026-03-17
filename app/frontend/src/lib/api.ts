import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { supabase } from './supabase';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  async (config) => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        config.headers = config.headers || {};
        config.headers['Authorization'] = `Bearer ${session.access_token}`;
      }
    } catch (error) {
      console.error('Failed to get session for API request:', error);
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error) => {
    if (error.response?.status === 401) {
      await supabase.auth.signOut();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;

// Members
export const getMembers = (): Promise<AxiosResponse> => api.get('/members');
export const getMember = (id: string): Promise<AxiosResponse> => api.get(`/members/${id}`);
export const addMember = (data: any): Promise<AxiosResponse> => api.post('/members', data);
export const updateMember = (id: string, data: any): Promise<AxiosResponse> => api.put(`/members/${id}`, data);
export const deleteMember = (id: string): Promise<AxiosResponse> => api.delete(`/members/${id}`);

// Repertoire
export const getRepertoire = (params?: any): Promise<AxiosResponse> => api.get('/repertoire', { params });
export const getPiece = (id: string): Promise<AxiosResponse> => api.get(`/repertoire/${id}`);
export const addPiece = (data: any): Promise<AxiosResponse> => api.post('/repertoire', data);
export const updatePiece = (id: string, data: any): Promise<AxiosResponse> => api.put(`/repertoire/${id}`, data);
export const deletePiece = (id: string): Promise<AxiosResponse> => api.delete(`/repertoire/${id}`);

// Events
export const getEvents = (params?: any): Promise<AxiosResponse> => api.get('/events', { params });
export const getEvent = (id: string): Promise<AxiosResponse> => api.get(`/events/${id}`);
export const createEvent = (data: any): Promise<AxiosResponse> => api.post('/events', data);
export const updateEvent = (id: string, data: any): Promise<AxiosResponse> => api.put(`/events/${id}`, data);
export const deleteEvent = (id: string): Promise<AxiosResponse> => api.delete(`/events/${id}`);
export const getUpcomingEvents = (): Promise<AxiosResponse> => api.get('/events/upcoming');

// Attendance
export const bulkAttendance = (data: any): Promise<AxiosResponse> => api.post('/attendance/bulk', data);
export const getEventAttendance = (eventId: string): Promise<AxiosResponse> => api.get(`/attendance/event/${eventId}`);
export const getMemberAttendance = (memberId: string): Promise<AxiosResponse> => api.get(`/attendance/member/${memberId}`);
export const getAttendanceReport = (): Promise<AxiosResponse> => api.get('/attendance/report');
export const updateAttendance = (id: string, data: any): Promise<AxiosResponse> => api.put(`/attendance/${id}`, data);

// Practice
export const getAssignments = (): Promise<AxiosResponse> => api.get('/practice/assignments');
export const getAssignment = (id: string): Promise<AxiosResponse> => api.get(`/practice/assignments/${id}`);
export const createAssignment = (data: any): Promise<AxiosResponse> => api.post('/practice/assignments', data);
export const updateAssignment = (id: string, data: any): Promise<AxiosResponse> => api.put(`/practice/assignments/${id}`, data);
export const deleteAssignment = (id: string): Promise<AxiosResponse> => api.delete(`/practice/assignments/${id}`);
export const logPractice = (data: any): Promise<AxiosResponse> => api.post('/practice/progress', data);
export const getPracticeProgress = (params?: any): Promise<AxiosResponse> => api.get('/practice/progress', { params });

// Arrangements
export const requestArrangement = (data: any): Promise<AxiosResponse> => api.post('/arrangements/request', data);
export const getArrangements = (): Promise<AxiosResponse> => api.get('/arrangements');
export const getArrangement = (id: string): Promise<AxiosResponse> => api.get(`/arrangements/${id}`);
export const updateArrangement = (id: string, data: any): Promise<AxiosResponse> => api.put(`/arrangements/${id}`, data);
export const deleteArrangement = (id: string): Promise<AxiosResponse> => api.delete(`/arrangements/${id}`);

// Exports
export const generateExport = (data: any): Promise<AxiosResponse> => api.post('/exports/generate', data);
export const getExportJobs = (): Promise<AxiosResponse> => api.get('/exports/jobs');
export const getExportJob = (jobId: string): Promise<AxiosResponse> => api.get(`/exports/jobs/${jobId}`);
export const getExportPack = (projectId: string): Promise<AxiosResponse> => api.get(`/exports/pack/${projectId}`);
export const downloadExport = (jobId: string): Promise<AxiosResponse> => api.get(`/exports/download/${jobId}`, { responseType: 'blob' });

// Customer
export const getCustomerStats = (): Promise<AxiosResponse> => api.get('/customers/me/stats');
export const getCustomerMe = (): Promise<AxiosResponse> => api.get('/customers/me');
export const updateCustomerMe = (data: any): Promise<AxiosResponse> => api.put('/customers/me', data);

// Utility
export const healthCheck = (): Promise<AxiosResponse> => api.get('/health');

export { api };
