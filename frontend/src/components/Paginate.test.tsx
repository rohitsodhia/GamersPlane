import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useNavigate } from "@tanstack/react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Paginate from "./Paginate";

vi.mock("@tanstack/react-router", () => ({
	useNavigate: vi.fn(),
}));

describe("Paginate", () => {
	const navigate = vi.fn();

	beforeEach(() => {
		navigate.mockClear();
		vi.mocked(useNavigate).mockReturnValue(navigate);
	});

	it("renders nothing when there is only one page", () => {
		const { container } = render(
			<Paginate numItems={5} itemsPerPage={10} current={1} onPageChange={vi.fn()} />,
		);
		expect(container).toBeEmptyDOMElement();
	});

	it("shows the current page and surrounding page numbers", () => {
		render(<Paginate numItems={100} itemsPerPage={10} current={5} onPageChange={vi.fn()} />);

		expect(screen.getByText("5 of 10", { exact: false })).toBeInTheDocument();
		for (const page of [3, 4, 5, 6, 7]) {
			expect(screen.getByRole("button", { name: String(page) })).toBeInTheDocument();
		}
	});

	it("hides first/prev on the first page and last/next on the last page", () => {
		const { rerender } = render(
			<Paginate numItems={50} itemsPerPage={10} current={1} onPageChange={vi.fn()} />,
		);
		expect(screen.queryByRole("button", { name: "<< First" })).not.toBeInTheDocument();
		expect(screen.queryByRole("button", { name: "<" })).not.toBeInTheDocument();
		expect(screen.getByRole("button", { name: ">" })).toBeInTheDocument();
		expect(screen.getByRole("button", { name: "Last >>" })).toBeInTheDocument();

		rerender(<Paginate numItems={50} itemsPerPage={10} current={5} onPageChange={vi.fn()} />);
		expect(screen.queryByRole("button", { name: ">" })).not.toBeInTheDocument();
		expect(screen.queryByRole("button", { name: "Last >>" })).not.toBeInTheDocument();
	});

	it("calls onPageChange when a page button is clicked", async () => {
		const user = userEvent.setup();
		const onPageChange = vi.fn();
		render(<Paginate numItems={50} itemsPerPage={10} current={2} onPageChange={onPageChange} />);

		await user.click(screen.getByRole("button", { name: "3" }));

		expect(onPageChange).toHaveBeenCalledWith(3);
		expect(navigate).not.toHaveBeenCalled();
	});

	it("also calls navigate to update the URL when updateUrl is set", async () => {
		const user = userEvent.setup();
		const onPageChange = vi.fn();
		render(
			<Paginate
				numItems={50}
				itemsPerPage={10}
				current={2}
				onPageChange={onPageChange}
				updateUrl
			/>,
		);

		await user.click(screen.getByRole("button", { name: "<< First" }));

		expect(onPageChange).toHaveBeenCalledWith(1);
		expect(navigate).toHaveBeenCalledTimes(1);
	});

	it("disables the button for the current page", () => {
		render(<Paginate numItems={50} itemsPerPage={10} current={3} onPageChange={vi.fn()} />);
		expect(screen.getByRole("button", { name: "3" })).toBeDisabled();
	});
});
