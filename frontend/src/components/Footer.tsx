import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { referralLinksQueryOptions } from "@/queries/referralLinks";

function Footer() {
	const { data } = useSuspenseQuery(referralLinksQueryOptions);

	return (
		<footer>
			<div className="page-wrap">
				<ul>
					<li>
						<Link to="/tools/">Tools</Link>
					</li>
					<li>
						<Link to="/systems/">Systems</Link>
					</li>
					<li>
						<Link to="/characters/">Characters</Link>
					</li>
					<li>
						<Link to="/games/">Games</Link>
					</li>
					<li>
						<Link to="/forums/">Forums</Link>
					</li>
					<li>
						<Link to="/gamersList/">The Gamers</Link>
					</li>
				</ul>
				<ul>
					<li>
						<Link to="/faqs/">FAQs</Link>
					</li>
					<li>
						<Link to="/about/">About GP</Link>
					</li>
					<li>
						<Link to="/contact/">Contact Us</Link>
					</li>
					<li>
						<Link to="/privacy/">Privacy Policy</Link>
					</li>
					<li>
						<Link to="/community_guidelines/">Community Guidelines</Link>
					</li>
				</ul>
				<ul>
					{data.referralLinks.map((link) => (
						<li key={link.key}>
							<a href={link.link} target="_blank">
								{link.title} Referral Link
							</a>
						</li>
					))}
					<li>
						<form
							action="https://www.paypal.com/cgi-bin/webscr"
							method="post"
							target="_top"
						>
							<input type="hidden" name="cmd" value="_s-xclick" />
							<input
								type="hidden"
								name="hosted_button_id"
								value="6VHQ2BP4AS7L6"
							/>
							<input
								type="image"
								src="/images/support_us.png"
								border="0"
								name="submit"
								alt="Gamers' Plane Donation Link"
							/>
							<img
								alt=""
								border="0"
								src="https://www.paypalobjects.com/en_US/i/scr/pixel.gif"
								width="1"
								height="1"
							/>
						</form>
					</li>
				</ul>
			</div>
		</footer>
	);
}
export default Footer;
