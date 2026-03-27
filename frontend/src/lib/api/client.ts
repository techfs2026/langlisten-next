import axios from "axios";

const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export const apiClient = axios.create({
    baseURL: "",
    timeout: 30000,
});

// response interceptor — unwrap data, normalize errors
apiClient.interceptors.response.use(
    (res) => res,
    (err) => {
        const message =
            err.response?.data?.detail?.message ||
            err.response?.data?.detail ||
            err.message ||
            "Unknown error";
        return Promise.reject(new Error(String(message)));
    }
);

export const API_BASE = API_BASE_URL;