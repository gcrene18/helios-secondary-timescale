"""
StubHub API client for fetching ticket listings.
"""
from typing import List, Dict, Any, Optional
import aiohttp
import asyncio
import json
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import random

from ..core.logging import get_logger, console
from ..config.settings import settings
from ..domain.listing import Listing
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

logger = get_logger(__name__)

class StubHubClient:
    """
    Client for interacting with the StubHub API.
    
    This class is responsible for fetching ticket listings from the
    StubHub API for tracked events, with retry capability and error handling.
    """
    
    def __init__(self, base_url: str = None):
        """
        Initialize the StubHub API client.
        
        Args:
            base_url: Base URL for the StubHub API
        """
        self.base_url = base_url or settings.stubhub_api_base_url
        
    async def get_listings(self, viagogo_id: str) -> List[Dict[str, Any]]:
        """
        Get ticket listings for an event.
        
        Args:
            viagogo_id: The viagogo event ID to fetch listings for
            
        Returns:
            List of ticket listings
        """
        url = f"https://pro.stubhub.com/api/Listing/GetCompListingsByEventId?viagogoEventId={viagogo_id}"

        logger.info(f"Fetching listings for event with viagogo ID: {viagogo_id} with URL: {url}")
        
        # Create custom headers to mimic browser
        headers = {
            'accept': 'application/json',
            'accept-language': 'en-US,en',
            'activeaccountid': '34a5599e-244a-4aab-8541-a7bc6723552e',
            'content-length': '0',
            'origin': 'https://pro.stubhub.com',
            'priority': 'u=1, i',
            'referer': f'https://pro.stubhub.com/inventory/event?eventId={viagogo_id}',
            'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            'Cookie': '_rvt=paVmhxcdCkK9SpvLdZx7TEx2ljANWZokYJexFdEPPsqIJFVM7xhohexQgUk__ppSs8hxKsvAnh1Smtn9JW-mwP2ASUkFBaBTTWivmNpjmF41; d=fq2heKDh3QGafB4VUCX7RLVvVG1iA2LLh768uw2; s=POn7DgMU7EGffk7Qse2bAn4ti6kUct0I0; wsso-session=eyJ1bCI6bnVsbCwidXBsIjp7Im4iOiJBc2hidXJuIiwicyI6ZmFsc2UsImxnIjotNzcuNDg4LCJsdCI6MzkuMDQ0LCJjdCI6IlVTIiwic3JjIjoiSVAiLCJkdCI6IjAwMDEtMDEtMDFUMDA6MDA6MDArMDA6MDAifSwiZCI6bnVsbCwicnYiOnsiYyI6W10sImUiOltdLCJsIjpbXSwicnRjX3UiOm51bGwsInJ0Y19ldCI6IjIwMjUtMDQtMDJUMTg6MzI6MDQuNDQxMzk2N1oifSwiZmMiOnsiYyI6W119LCJwIjpbXSwiaWQiOm51bGx9; _gcl_au=1.1.1371187429.1743618726; _gid=GA1.2.693869992.1743618729; wsu.2=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NDM2MjAwMDksImF1ZCI6InZnZyIsInNpZCI6ImVhZmM3NTVhLTUwNjMtNDY3ZC1hY2VjLTAyY2I5NGRlYWExYSIsImp0aSI6ImQ4MmUwOWViLTlmNDUtNGI4Yy05MDMwLWZlZjI1ZWZlNWRkNyIsImpyaSI6IjMzYmZlZmNiLTljYjUtNGI3Mi1hNjZiLWVkNWUyYWMxNzllYSIsImlzcyI6InYyIiwic3ViIjoiODE4MmY5NjgtODcxOS00NTQzLWJhMGUtNTM5YTczYWIwZGZmIiwiYW0iOjQwMCwiYXMiOjIsInIiOiIiLCJpZyI6ZmFsc2UsImllYyI6ZmFsc2V9.eeWcqpqrxTonjI1smhWgXSr80gARxMcz8DTkocSqKuZivn4qVgD25brDJAX1QB6JpDB5_gtkBo5oqZ8U2TLTe7u2j0asFIeLFka9rr2kSxIEUz-tJf_kd3usLoxjnKyWjNlc6paGHk94msONYznFA0p3qLOHnfJZuLmHAQwyxprIndDBvzyBhb5TYtF1YkBL_DX3OXRu3R2VR-PXvIsqMdDtT43H2Hsgfm35E5h7pq_dXhd-RRyPXg2c_3x95nB0jnP3JZpGbYNwDI0g9uE47uGeY9ZycXhCcStscOjN6yNr-qDUeLqUqHDN4XQ_vIvpcF4lWaX7hp1deWE0nqUY_Q; wsp=eyJ1IjoiQ2hlbHNpZSBMYWNvc3MiLCJsIjoxMDMzfQ2; wsso=eyJ1bCI6eyJuIjpudWxsLCJzIjpmYWxzZSwibGciOi03Ny40ODgsImx0IjozOS4wNDQsImN0IjoiVVMiLCJzcmMiOiJERVZJQ0UiLCJkdCI6IjAwMDEtMDEtMDFUMDA6MDA6MDArMDA6MDAifSwidXBsIjp7Im4iOm51bGwsInMiOmZhbHNlLCJsZyI6MC4wLCJsdCI6MC4wLCJjdCI6bnVsbCwic3JjIjoiREVWSUNFIiwiZHQiOiIwMDAxLTAxLTAxVDAwOjAwOjAwKzAwOjAwIn0sImQiOnsidHlwZSI6MCwiZGF0ZXMiOnsiZnJvbSI6bnVsbCwidG8iOiI5OTk5LTEyLTMxVDIzOjU5OjU5Ljk5OTk5OTlaIiwiZXhwaXJhdGlvbiI6bnVsbH19LCJydiI6eyJjIjpbXSwiZSI6W10sImwiOltdLCJydGNfdSI6bnVsbCwicnRjX2V0IjoiMjAyNS0wNC0wMlQxODozMzozMC41OTEzMTA1WiJ9LCJmYyI6eyJjIjpbXX0sInAiOltdLCJpZCI6bnVsbH0=; auths=1; _uetsid=c7439dd00ff011f09331ef9243ebbbf3; _uetvid=c743ad300ff011f0835f59ff9f1bfaa0; _ga_1686WQLB4Q=GS1.1.1743618725.1.1.1743618810.0.0.0; _ga=GA1.1.817935059.1743618726; ai_user=RgGW9/efo/7P9Wn8VQ/oId|2025-04-02T18:34:15.090Z; ac.2=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NDM2MjAwNTgsImF1ZCI6InZnZyIsInNpZCI6ImQ0NzBkNGI1LWYxOTItNDhiNS1iMmNlLTY4MjRkMjEzZjBkOSIsImp0aSI6IjcwMDY3YzM5LWJkMGMtNDNmNy1hMzM2LTEwMzMwNzg1NTRhMSIsImpyaSI6IjA4ZDU4NGExLWFmYjgtNDEwZi04M2RjLTQ3ODQzNTEyMTJmOSIsImlzcyI6InYyIiwic3ViIjoiODE4MmY5NjgtODcxOS00NTQzLWJhMGUtNTM5YTczYWIwZGZmIiwiYW0iOjM4NSwiYXMiOjIsInIiOiIiLCJpZyI6ZmFsc2UsImllYyI6ZmFsc2V9.e80A_Jbybm1A8FzFQ3RqWl-erWu8bta3xtyUDASQotXeLJs1y8FtLAPqp5RpIRz7iXV6VzJR7c5VT_rP8hra6F-NCU12b7wa8_IlBbi-fJZ2bFCETbNkJmNyq-Qy2cFgu1m_kVTGDvG3THdfZ--P93tF1o6NFZBVaYJAmnlsbXLrLj-4pLhUUaBWMybf_aO_ABGv5L1t2o2Gr8QkbeZTSpGRJycJff3y8MySg3yKs9ibb99kVpjdFS8et3wQxNVN4RbsAb_FtjXDQsr6p7c8cvS4lpaF-g8hyDdG_J06r4qOTfmVYCHQ7wSfY3U4ui0-AfzGMOrUEMh67karK9XQFQ; p=eyJfX3R5cGUiOiJWaWFnb2dvLklkZW50aXR5U2VydmljZS5Qcm9maWxlLCBWaWFnb2dvLklkZW50aXR5U2VydmljZSIsInUiOiJDaGVsc2llIExhY29zcyIsImwiOjEwMzMsImMiOm51bGx90; _abck=AC54163473FF2945174F468C186BF65F~0~YAAQS97aF7XzxtqVAQAAEmDI9w2oeDXqTmHC07AXj12UguG/qvbp3dIKv38/hN2rgI+xwxO8sCsyvbGzp7FPnb7cB68k/EWOfQ+MPk680o+RaQeHW++E32t09SaGIxnVPNQNAd0Qd8+QbUTGPXHZQldNw+d62P/Y/b6HhfQUTG+ZQzDu4ySF77mrJRo/1v4JaHTdJdDSiKQmIB8zNfbRsu75uDN4G0ymMSUoo4vhfBIm4st0Vz6cLUOykWKwzrFDfG8lNZnCK/RlaUxDHnynfRbE+9hzRX1mppVOlL5MRBhz6kwGzwbhO2JhOXaJ/ZTuPlo0aJl7pmmYpg5LfgnBtiRW2ydLKqzBaDwU+Qm+JE+KTatcPbCgaqsn2DtEZBfxkuKyP17ep42kzbxcy4AXDY3kghWbjQKLNiHeKsmTgZot4nxcsYC4y7Uj0Dq788nF6D9Z1rcJgzzf8kv+tVJj+R953rt6ymuf1cFRqyfW6rB+E2lssn/q8HI0oGxb706dCY53JJaGbXEcxoJTYm6LBTi6j5Yq+TScVnWnwKA4CCpRXNRS053+1erUGn8BP5NGSY6yAmDYeW3L72BvusKeyGc1dhp0adwu72h2Zoxn+b+rVFaguD2dh/cTvADCCkLod1PsFkvn0+dlacU7n8TjI/GTu8jD5GNjn1EiQ0uf1tXbIw/cUISE4y/ujBSjnam4aLEI5Syjdpa5YjWhu1ZlzRywcZBOUD/KsjuUWnYM1G+peBcinY1e0IanNxLgW0kJ4R6x9RDIa8N4Hmk23DTbE39kY4Q6Qgfg76J2GpWO+kJH/pEd4LvibvzzPdBU1ENBLkTO4kGEOyG6CWWF/VyxP72SHKqFM3vegmOL1y0LsRuC~-1~-1~-1; bm_sz=3560638D18DF4DE252B1C0E470C00553~YAAQS97aF8zzxtqVAQAAamDI9xvXwXzA5CiK4gqZrMYFDWAdUKecrcwDkqZxvD7RYbKccAJyMrzYe78V5D7wyQm7eox+LiKtLehU8wIXSGC6pGmPZyzBNxRwuNBgeCKQqQMJqP+WGbsEBSlIqNFoLTPRVylgOWN3sSHH5Ig2m6JkvrY+1aamnnL0sVsceJX/N5Fi5PTibJIbWIRE5qZVNp0qK5lQ8hnzWFHF2bOQB/stGdBxluW9rNXl78OFKRcONJTv/NKVGlwCodbxHrQJJA9nnegFYRcqUQd/HSj+7pEL0Jca+ZW32FstBPwCrvJIYjE3SX+s+S/oeZ69hgv5DtWq6poGVgZLgwraG2FstnCi3zeg13HStf6No10gtrJu0WOoKXbQ+iQXLD4aYia9PZQXA2SKFwu25m376sNuQjEfOvHWhwbD9KjUIc1cziPCWgeC2KiGmkn/lzb6tA==~3486768~4535621; ai_session=02yWqhn4LL7MrT94B6O45N|1743618855092|1743618859614; ak_bmsc=2DA9D8564C027D9AA2F2358CDBE4D9B7~000000000000000000000000000000~YAAQVWncF5oYW/OVAQAAr9DJ9xuzhf0NnCzwc4UcWTYkzmqiXqz/3UjP34dY3UmPZGC/OM7wKbiFm0cAAgVl4lO9qJrzWH2Kr99qQSzbXUe0T6qWuRAseEH+BlNDVPtbjsWSgs6wUHRnfoyEQ8zI1rohg7AQqdCD5a7jOdapZBz2Fm8EFJXIbP9TdlwFrXvgaWo3E7/Og6GU/UjiAdt8vLix/YmJYC6QaSZ444kNltjVoIumXhbmMOSOZkXcGcIrNrK8qHs7DXxAlez/vzX4qrdJQKTONx2gLhes9dttW0JZ3CHy3QEBwsgM25x1Xs/MdTcQQvTPa/FjINcYOPLe9QUhtOyImb1LC6dSpb5LEvLQ18jweCPAFGUO4UInwecQ8HQx+L8hnzhCtYiz7myncd6Jj3IuuNz0C8P+WkBl; stubhub.onehub=CfDJ8P-eQo1sBbNMhxkqI1DYPArsi8d0vlb2-BRNsi9-KeX__uTweLhnHSqY0q4lhGv0t1H-hX8_VNfRcXmJDot7zhF_OJiwIyoHitbmI_9Fk1roSD6Ve2TfrJTmsyQ2hOwGORULwQVbZ8BFZUJbUwQJF8TPaWZ_vUCYcBOL480Q61lQa4vl1ytRH0s5wxQ0PrzJoI6SoT5AlMncOpC5Se7o03pQlbhFWilYkZXd4XCDsbX5KurANjqS9REFkIkI8EUd4xzRiracCL_h1in5K7-1bOmacPLW-mvg-WshV2XC3BqR6NfQIN6Nm7XOOYvM5-I_9ZEC-U8iLIXLhCfwF6M0RCjq8j3QhgNx2WEJjIkJciBVwiuY7FxcJgWjd2pekNJr_ivJtE5m-YdmGwkJY69ITVqYEP3qqlvLic9cYsYu0o_x-EcL_rHVFHzPHAKBY4qWJBDmhWAxpo_SPoApgAO1-SNZXYPRJ2OKyZ-wH6NZ15Ep5ROtVKueD37beuZ8Ar0cxDjyykJwMYVfazuvWElVZQjdXWLdBBVKd80Uc7Pf4Q5kexmw_USToPE_ci3WY81MQJzHv4_Q0H_SXZJVvxjmAYun5mGFu18en78ZS8BxYVoMkMIud3fI4d0lCRBcuefFCtsLn22gBe7SVDjiYNm4FFhYjxFUnr8landy4ZAso7KJtMXCfD29ze7aF_bdAszyVTiDq0z8zqPhMXojJwL0sAF2sDGc7wqb-r6NZQAV42CQNc_V3C9iqbJMuhXu7vvLrYyRapCy_nV1aCorq4wTotKArjnWfWYYulo9VtBhLU435fiP-CNSYC4wHr9fQAavHCEErV_Vf-OzbGXCjTZcR0olNmlOc5rK5jhjZtnympfE5QK-6OSXHbZkl0oenphN99LEzMwE9-6QpNc-7lTePG9_2cNlT6hhxnbl57zdz1C_GVT5wsDk5Sft9I7PNVqJid17QQPqwq0j0H2Pip2v3o_G9ucthlM42QX21EPwfQhNswYUk1KT-5KL8PFmPloar8UdWDI_Pl3aKuG5PhtR6i6b7J1H0DSc72Goep3rgWuQ4oMgQpFAOZjDwbdAhaCQZ7BL0cGFYagOubNbAB4Nkm5BsyNBFKNgOfSUU45aqlz_zvmbbmDaRBtTRfIsFhbxYKIcQs0KE26WKRjc9QFgdT6PEA7aVKOdjnyxPRS_Sw1S4l9xGot_mNWB153pwKNOBRdeCSpiv20F5FCezaCKfXqiCk2L2yY8oQLvQ_ACIjUrPqv-lNOIpRhuz5t4l5uA8c_FJ8jtdzOcaJ5QZt4IQGmyl92IEw7TbrFQzJDyR9UvsC106ztd-XXKkfZqYHYP31nBOvNXSKxz83YuBX1g34LXuPMLU9qrECWLXUhcAcbgtBek-_FO46-hcd0KXVicMkCp-f8blDKeES7zqYtMtqNerNH6c6D8JNpXrMvsPcpwAbIBljctiRHk8VtVvPf8xB5kzGqWSQfxvL0rUDFAfLGEbRkmWTlIGIrR54fcqP8IRhUIQE9JsXlCM70QhXN7dkDijxwBYlwZMXEuY-DyO5Xrx1dH5qlmf6Wj--nxs3-6FWEAeABP3KyaVQ4OwuFnWq48rZRHuBTssUJSXCxAmbq1FpSwvSdqUHOTPaKbPtulvvspn8hj9lltAAQqysFjE0d4DPJevk7_mN8WQOBbjave7w060Zdd5nBda_wPHP-IIibxGIRkEzhzeUgSJIU2p3ovh5o0ea6SG_qZesS03WdgPmWpoe1WzKRiqy1nbccTcu8YktvM3YC52Z371Zki-mloJLcIJaPTxEGg7K9UxeI-YYw1yr7yZ5Yf64V1tqLQhcr6Tl3Cmqpede69KTcDQUh-T4HEIsuPwVin1fjp1KRVGJZ8EZIsaEb4wHgskIEKkaqGZ38-3KAzHAJTiz1xpg5zsVFSDRfhkKlUDhuL_lCp3kKQfL__XiUEStewwUpxVO0vucwm6f0WMNx2xShY9gkqIbDBzFI92PiXE-2sg5fMOidHbFa1YAD8YTloBOOpkks1ojLPkpwokmx8LygJHO6RFC_-5MNQS_unTg03lkDJJOn_vAXVx2ICp6yS3RtRt31LNXpssOUmjfUQX_ZzRDZiwXpY0XHcGNFKUW6_8GciCZOg3xWjtQ_iknH57JsmE8bAQBlKbeQwteBCoWuoYywmx8_bKRK8NsZ5nNYGwogAgbARkBLDydRICUVhNsBG-E897P3azK7ERCVgApytpITJ6yoWxId7IdL7Zg1Mi7Q1Wx26tGZv0pz1k4meAZb5GRnHDqu5jtjuGd3ueRgHgwnU3neUypazNLVQGicNuHKRIMo6zDw7WTN61ljO3A8lejSODc6MQ59shSPK1iGgcmuw6KUsbxuIXpUT5-gHA9bmHFvlMmXojMupjQB9r9ITISowrhyX4rnDD43N7KsNs1_GAxgkZqLws4-P4s49SfnMHLpvATXZcPfiHW-U82rcTHAMnlM2h5gahxyOWFmdYd20q9Rrj6sUirwRxAztOed8GmYP6V7_hERENMCSm5ABjdmX03xxR7jvJrsCZEsBa8W6y8RYSBUnO-nVDZtxOXkaJz2c0lu2rlggA2q00NLend5K1Jsqg8fgBsmoUS656LJ44sznweMmGX5d49SVLr_iGXSHpUzmzFZxRGvSSj3PUyUtxthsobCGY4lMs9L9gj3c0u3Dsq9zkfxfbNwgvv_GTBg2RHzREWJB6dkMUtjgV_1YGqRja7WJM1i31Za4b9EzGELeXZUA53Lm51ZBdj0wsxj206rnArJJAQKYayOpmBN6POmcjECzfhWG-d88cZOt60ncPfrbDkp6-duPBZxyzt45OlpdyWHQJ4Oi4i_43DQs-w6urM5TWSVtQH1A_0ahwh0KleUFXgTJivM1onwdgMaQvTHByr0y_5g7115Gwo_egtOQaHwRkk4tyiY1CrbmX7BB8X1oeHAtFRzbg1tkoKc9eeo66eZadoifmK9MepIRiEBXV_ViZEphJjIhQQ; bm_sz=2D845D2F4D798FAD4AF3914356CF7202~YAAQVWncF5UiW/OVAQAA8S3K9xu6fn7dkZ6WkKO23q4/JB4CDAIquzo0fiSH6KToZYB6i9uXjE2H9eKV8iRHT6WGtKcsy3hIy/mgNLQAqxJXHmRpD145BeXKQb6XEPZmPQfyR7RtVXbb5cYLjY84PsEYYeGIQoMSRsZ1rp8m5CyeqH0a2f8X+W6hw/0s5PnR0VtpVa0+ZZeW4tLP2uNcCVEUqXy/E8+pRnXFvEIgL2AbkTH7YVAE76+nxzodNDf6/e0=~1; _abck=B7A0EAE74E8EBDB314791779CEF3726F~-1~YAAQxoXYF4TBEKePAQAAnVyB6Ayq0ruc9JvMV6PGGBy14SSKVbDK+xUeSGFmt6s5DP5TDfbpRuR+vuoCoy3Qtyb+POxzC658vmBNbFMCl/3kVVytCCLLqcBuLHVgQQLCJa01zGzBBv30s3GAvTEdMLqOLj1SufU33jCsXxmMo6zgiliHg436GeMqkNmCdUmbDO1gnLc3oBzdiykkWId077f9HDInB2bJZ9vBvbruFXy0Aj6CFDPu6Z0lYwbZT19UKF9ePVOg4YAvw894XqyVO9fO23T0p7hGlQKIuCjbYzd+XsEjxOmLTdRud3dJ36jfO0bMCwqPAPm9UoGFrJYyumgzFKFUrPtu8tCRyhgQkcH5V3vw0bWwEKZo+d1bwKyVSpJMdKUhxzLlypTeUzfH7z/+nuWPg4wui5aDra74Al8jVSL6QiI=~-1~-1~-1; d=OBc6-Zvy3AHnJ5fJqCKWSq0sCS5zA5BPMGTx8w2; wsso=eyJ1bCI6eyJuIjpudWxsLCJzIjpmYWxzZSwibGciOi03My45OTcsImx0Ijo0MC43NSwiY3QiOiJVUyJ9LCJ1cGwiOnsibiI6Ik5ldyBZb3JrIiwicyI6ZmFsc2UsImxnIjotNzQuMDA2LCJsdCI6NDAuNzEzLCJjdCI6IlVTIn0sImQiOnsidHlwZSI6MCwiZGF0ZXMiOnsiZnJvbSI6bnVsbCwidG8iOiI5OTk5LTEyLTMxVDIzOjU5OjU5Ljk5OTk5OTlaIiwiZXhwaXJhdGlvbiI6bnVsbH19LCJydiI6eyJjIjpbeyJ0IjoiMjAyNC0wNi0wMVQwMDo1NTo1My4zOTkxMjQzWiIsImlkIjoyOTUzNn0seyJ0IjoiMjAyNC0wNi0wMVQwMjozMjoxMi41MzcwNTMxWiIsImlkIjo1NjUyNX0seyJ0IjoiMjAyNC0wNi0wNVQxMzowNTo0Mi44Njc5MTc3WiIsImlkIjo1NTMyfV0sImUiOlt7InQiOiIyMDI0LTA2LTAxVDAwOjQzOjI2Ljc2NDIxNTFaIiwiaWQiOjE1MzUzMDY4M30seyJ0IjoiMjAyNC0wNi0wMlQxNjo1MTo0NS42NTcxMzkzWiIsImlkIjoxNTM1MDExMTV9XSwibCI6W10sInJ0Y191IjpudWxsLCJydGNfZXQiOiIyMDI0LTA2LTAxVDAwOjM2OjIxLjgyMDExNDZaIn0sImZjIjp7ImMiOltdfSwicCI6W10sImlkIjpudWxsfQ=='
            }
        
        proxy = "http://ggFpDGhEtc:3JbtLBMgeA@142.173.179.233:5998"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(url, headers=headers, proxy=proxy) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Successfully fetched listings for event {viagogo_id}")
                        logger.info(f"Data is: {data}")
                        return self._parse_listings(data)
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"API error for event {viagogo_id}", 
                            status=response.status, 
                            error=error_text
                        )
                        return []
        except Exception as e:
            logger.error(f"Failed to fetch listings for event {viagogo_id}", error=str(e))
            return []
    
    def _parse_listings(self, response_data: Any) -> List[Dict[str, Any]]:
        """
        Parse ticket listings from the API response.
        
        Args:
            response_data: Raw API response data (a list of listings)
            
        Returns:
            List of parsed ticket listings
        """
        listings = []
        
        try:
            # StubHub Pro API returns a direct list of listings
            for item in response_data:
                if not isinstance(item, dict):
                    continue
                    
                listing = {
                    'section': item.get('section', 'Unknown'),
                    'row': item.get('row'),
                    'quantity': item.get('availableTickets', 1),
                    'pricePerTicket': float(item.get('sellerAllInPrice', {}).get('amt', 0)),
                    'totalPrice': float(item.get('sellerAllInPrice', {}).get('amt', 0)) * item.get('availableTickets', 1),
                    'currency': item.get('currencyCode', 'USD'),
                    'listingUrl': f"https://www.stubhub.com/listing/{item.get('listingId')}"
                }
                listings.append(listing)
            
            logger.info(f"Parsed {len(listings)} listings from API response")
            return listings
        except Exception as e:
            logger.error("Error parsing listings from API response", error=str(e))
            return []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def get_listings_with_retry(self, viagogo_id: str) -> List[Listing]:
        """
        Get ticket listings with retry logic and convert to domain models.
        
        Args:
            viagogo_id: The viagogo event ID to fetch listings for
            
        Returns:
            List of Listing domain models
        """
        raw_listings = await self.get_listings(viagogo_id)
        
        if not raw_listings:
            return []
            
        # Convert to domain models
        return Listing.from_list(raw_listings, viagogo_id)
    
    async def fetch_all_listings(self, viagogo_ids: List[str]) -> Dict[str, List[Listing]]:
        """
        Fetch listings for multiple events concurrently.
        
        Args:
            viagogo_ids: List of viagogo event IDs to fetch listings for
            
        Returns:
            Dictionary mapping viagogo IDs to lists of listings
        """
        results = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"Fetching listings for {len(viagogo_ids)} events...", total=len(viagogo_ids))
            
            for viagogo_id in viagogo_ids:
                # Add some randomized delay to avoid detection
                delay = random.uniform(1.5, 4.5)
                await asyncio.sleep(delay)
                
                listings = await self.get_listings_with_retry(viagogo_id)
                results[viagogo_id] = listings
                
                progress.update(task, advance=1)
                
        return results
