import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";


export function classMerge(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

export class APIRequests {
    url: string;

    constructor(url: string) {
        this.url = url;
    }

    get(endpoint: string) {
        const requestOptions = {
            method: "GET",
        };
        return fetch(endpoint, requestOptions).then(this.handleResponse);
    }

    post(endpoint: string, body: object) {
        const requestOptions = {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        };
        return fetch(endpoint, requestOptions).then(this.handleResponse);
    }

    put(endpoint: string, body: object) {
        const requestOptions = {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        };
        return fetch(endpoint, requestOptions).then(this.handleResponse);
    }

    delete(endpoint: string) {
        const requestOptions = {
            method: "DELETE",
        };
        return fetch(endpoint, requestOptions).then(this.handleResponse);
    }

    handleResponse(response: Response) {
        return response.text().then((text) => {
            const data = text && JSON.parse(text);

            if (!response.ok) {
                const error = (data && data.message) || response.statusText;
                return Promise.reject(error);
            }

            return data;
        });
    }
}

export const gp_api = new APIRequests(<string>process.env.API_PATH);
