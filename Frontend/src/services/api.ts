/**
 * API service for communicating with the Python backend.
 */

const API_BASE_URL = 'http://localhost:5000/api';

export interface Category {
    id: string;
    label: string;
    prefix: string;
}

export interface Report {
    id: string;
    batch_id: string;
    category_id: string;
    timestamp: string;
    total_calls: number;
    successful_calls: number;
    report_file: string | null;
    userIds: string[];
    category_label?: string;
    category_prefix?: string;
}

export interface User {
    id: string;
    user_id: string;
    report_id: string;
    name: string;
    agreed: number;
    call_duration: number;
    call_date: string;
    loan_amount: number;
    credit_score: number;
    risk_level: string;
    audio_file: string | null;
}

export interface ReportWithUsers extends Report {
    users: User[];
}

// Health check
export async function checkHealth(): Promise<boolean> {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        return response.ok;
    } catch {
        return false;
    }
}

// Get all categories
export async function getCategories(): Promise<Category[]> {
    const response = await fetch(`${API_BASE_URL}/categories`);
    if (!response.ok) throw new Error('Failed to fetch categories');
    return response.json();
}

// Get reports by category
export async function getReports(category?: string): Promise<Report[]> {
    const url = category
        ? `${API_BASE_URL}/reports?category=${category}`
        : `${API_BASE_URL}/reports`;

    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch reports');
    return response.json();
}

// Get single report with users
export async function getReport(reportId: string): Promise<ReportWithUsers> {
    const response = await fetch(`${API_BASE_URL}/reports/${reportId}`);
    if (!response.ok) throw new Error('Failed to fetch report');
    return response.json();
}

// Get users for a report
export async function getReportUsers(reportId: string): Promise<User[]> {
    const response = await fetch(`${API_BASE_URL}/reports/${reportId}/users`);
    if (!response.ok) throw new Error('Failed to fetch users');
    return response.json();
}

// Get single user
export async function getUser(userId: string): Promise<User> {
    const response = await fetch(`${API_BASE_URL}/users/${userId}`);
    if (!response.ok) throw new Error('Failed to fetch user');
    return response.json();
}

// Get audio file URL
export function getAudioUrl(filename: string): string {
    return `${API_BASE_URL}/audio/${filename}`;
}

// Get report PDF file URL
export function getReportFileUrl(filename: string): string {
    return `${API_BASE_URL}/reports/file/${filename}`;
}

// Get stats
export async function getStats(): Promise<{
    totalReports: number;
    totalUsers: number;
    totalAgreed: number;
    totalDeclined: number;
    categoryStats: Array<{
        id: string;
        label: string;
        report_count: number;
        total_calls: number;
        successful_calls: number;
    }>;
}> {
    const response = await fetch(`${API_BASE_URL}/stats`);
    if (!response.ok) throw new Error('Failed to fetch stats');
    return response.json();
}
