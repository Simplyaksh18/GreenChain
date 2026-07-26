import apiClient from './client';
import type { LoginRequest, LoginResponse, RegisterRequest, User } from '../types';

/** POST /auth/login → access_token */
export async function loginApi(credentials: LoginRequest): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/auth/login', credentials);
  return data;
}

/** GET /users/me → current user profile */
export async function getMeApi(): Promise<User> {
  const { data } = await apiClient.get<User>('/users/me');
  return data;
}

/**
 * POST /auth/register → created User
 * After successful registration, the user must log in separately.
 * The backend does NOT return a token on register.
 */
export async function registerApi(payload: RegisterRequest): Promise<User> {
  const { data } = await apiClient.post<User>('/auth/register', payload);
  return data;
}
